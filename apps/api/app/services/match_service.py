"""Job ↔ resume matching (PRD §16, §29, §36): deterministic steps around one decision model.

load job → load resume + profile → validate → build state → OpenJev (two phases) →
rubric formula → persist. Results are cached by input hash (resume text, profile, job content,
model revision, rubric version).
"""

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.matching.rubric import CURRENT_RUBRIC, RUBRICS, Rubric
from app.matching.scoring import (
    dim_id,
    evaluate,
    is_stated,
    met_id,
    phase_one_questions,
    phase_two_questions,
    stated_id,
)
from app.models import CandidateProfile, Job, MatchScore, MatchStatus, Resume
from app.providers.decision import (
    DecisionProvider,
    DecisionResult,
    DecisionUnavailable,
    ModelInfo,
    ScoreAnswer,
    YesNoAnswer,
)
from app.services.eures_workflow import Clock, utc_now

logger = logging.getLogger(__name__)

LIVE_STATUSES = (MatchStatus.QUEUED, MatchStatus.RUNNING, MatchStatus.DONE)
NOT_STATED = "not stated"


class JobNotFound(AppError):
    code = "JOB_NOT_FOUND"
    http_status = 404


class ResumeNotFound(AppError):
    code = "RESUME_NOT_FOUND"
    http_status = 404


class NoPrimaryResume(AppError):
    code = "NO_PRIMARY_RESUME"
    http_status = 409


class InputChanged(AppError):
    code = "INPUT_CHANGED"


# --- inputs -----------------------------------------------------------------------------------


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value).__name__)


def profile_hash(profile: CandidateProfile) -> str:
    data = {
        "target_roles": profile.target_roles,
        "skills": profile.skills,
        "years_experience": profile.years_experience,
        "industries": profile.industries,
        "education": profile.education,
        "certifications": profile.certifications,
        "languages": profile.languages,
        "preferred_locations": profile.preferred_locations,
        "remote_preference": profile.remote_preference,
        "work_authorization": profile.work_authorization,
    }
    raw = json.dumps(data, sort_keys=True, default=_json_default)
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class MatchInputs:
    resume_text_hash: str
    profile_hash: str
    job_content_hash: str
    model: ModelInfo
    rubric_version: str

    def input_hash(self) -> str:
        parts = [
            self.resume_text_hash,
            self.profile_hash,
            self.job_content_hash,
            self.model.revision,
            self.rubric_version,
        ]
        return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def gather_inputs(job: Job, resume: Resume, model: ModelInfo, rubric: Rubric) -> MatchInputs:
    return MatchInputs(
        resume_text_hash=resume.text_hash,
        profile_hash=profile_hash(resume.profile),
        job_content_hash=job.content_hash,
        model=model,
        rubric_version=rubric.version,
    )


def _items(values: list[str]) -> str:
    return ", ".join(values) if values else NOT_STATED


def _cap(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n[… truncated]", True


def build_state(rubric: Rubric, job: Job, resume: Resume) -> tuple[str, dict[str, bool]]:
    """PRD §30 layout. Unset profile fields say "not stated" instead of being guessed."""
    p = resume.profile
    languages = ", ".join(f"{lang['language']} ({lang['level']})" for lang in p.languages)
    resume_text, resume_cut = _cap(resume.raw_text, rubric.max_resume_chars)
    description, description_cut = _cap(job.description, rubric.max_description_chars)
    employer = (job.company.company_name if job.company else None) or job.employer_name
    years = p.years_experience if p.years_experience is not None else NOT_STATED
    lines = [
        "CANDIDATE",
        f"Target roles: {_items(p.target_roles)}",
        f"Skills: {_items(p.skills)}",
        f"Years of experience: {years}",
        f"Languages: {languages or NOT_STATED}",
        f"Education: {_items(p.education)}",
        f"Certifications: {_items(p.certifications)}",
        f"Industries of interest: {_items(p.industries)}",
        f"Preferred locations: {_items(p.preferred_locations)}",
        f"Remote preference: {p.remote_preference or NOT_STATED}",
        f"Work authorization: {_items(p.work_authorization)}",
        "",
        "Full resume evidence:",
        resume_text,
        "",
        "VACANCY",
        f"Company: {employer or NOT_STATED}",
        f"Role: {job.title}",
        f"Location: {job.location or NOT_STATED}",
        f"Employment type: {job.employment_type or NOT_STATED}",
        f"Workplace: {job.workplace_type or NOT_STATED}",
        "",
        "Description:",
        description,
    ]
    return "\n".join(lines), {"resume": resume_cut, "description": description_cut}


# --- requesting -------------------------------------------------------------------------------


async def _load_job(session: AsyncSession, job_id: uuid.UUID) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise JobNotFound("Job not found")
    return job


async def _load_resume(session: AsyncSession, resume_id: uuid.UUID | None) -> Resume:
    if resume_id is not None:
        resume = await session.get(Resume, resume_id)
        if resume is None:
            raise ResumeNotFound("Resume not found")
        return resume
    primary = await session.scalar(select(Resume).where(Resume.is_primary.is_(True)))
    if primary is None:
        raise NoPrimaryResume("Upload a resume first (Settings → Profile & resume)")
    return primary


async def _live_match(session: AsyncSession, input_hash: str) -> MatchScore | None:
    return await session.scalar(
        select(MatchScore).where(
            MatchScore.input_hash == input_hash, MatchScore.status.in_(LIVE_STATUSES)
        )
    )


async def request_score(
    session: AsyncSession,
    provider: DecisionProvider,
    *,
    job_id: uuid.UUID,
    resume_id: uuid.UUID | None = None,
    rubric: Rubric = CURRENT_RUBRIC,
) -> tuple[MatchScore, bool]:
    """Returns (match, created). An identical input returns the cached or in-flight match."""
    job = await _load_job(session, job_id)
    resume = await _load_resume(session, resume_id)
    inputs = gather_inputs(job, resume, await provider.model_info(), rubric)
    key = inputs.input_hash()
    existing = await _live_match(session, key)
    if existing is not None:
        return existing, False
    match = MatchScore(
        job_id=job.id,
        resume_id=resume.id,
        status=MatchStatus.QUEUED,
        input_hash=key,
        resume_text_hash=inputs.resume_text_hash,
        profile_hash=inputs.profile_hash,
        job_content_hash=inputs.job_content_hash,
        model_provider=inputs.model.provider,
        model_name=inputs.model.name,
        model_revision=inputs.model.revision,
        rubric_version=inputs.rubric_version,
    )
    session.add(match)
    try:
        await session.commit()
    except IntegrityError:  # a concurrent identical request won the race
        await session.rollback()
        existing = await _live_match(session, key)
        if existing is None:
            raise
        return existing, False
    return match, True


# --- running ----------------------------------------------------------------------------------


def _explain_score(answer: ScoreAnswer) -> dict[str, Any]:
    return {
        "expected_level": answer.score,
        "probabilities": answer.probabilities,
        "confidence": answer.confidence,
    }


async def run_match(
    session: AsyncSession,
    provider: DecisionProvider,
    match_id: uuid.UUID,
    *,
    clock: Clock = utc_now,
) -> MatchScore | None:
    """Execute a queued match. Transport failures put it back to QUEUED and re-raise
    (the queue decides whether to retry); other errors mark it FAILED."""
    match = await session.get(MatchScore, match_id)
    if match is None or match.status not in (MatchStatus.QUEUED, MatchStatus.RUNNING):
        return match
    started = time.monotonic()
    match.status = MatchStatus.RUNNING
    match.started_at = clock()
    match.attempts += 1
    await session.commit()
    log = {"match_id": str(match.id), "job_id": str(match.job_id)}
    logger.info("match_started", extra={"event": "match_started", **log})

    try:
        rubric = RUBRICS[match.rubric_version]
        job = await _load_job(session, match.job_id)
        resume = await _load_resume(session, match.resume_id)
        model = await provider.model_info()
        inputs = gather_inputs(job, resume, model, rubric)
        if inputs.input_hash() != match.input_hash:
            raise InputChanged(
                "The job, resume, profile or model changed after scoring was requested; "
                "score the job again"
            )
        state, truncated = build_state(rubric, job, resume)

        first: DecisionResult = await provider.decide(state, phase_one_questions(rubric))
        stated = {r.key: _yes(first, stated_id(r.key)) for r in rubric.hard_requirements}
        stated_keys = [k for k, p in stated.items() if is_stated(rubric, p)]
        second = (
            await provider.decide(state, phase_two_questions(rubric, stated_keys))
            if stated_keys
            else None
        )
        met = {k: _yes(second, met_id(k)) for k in stated_keys} if second else {}
        levels = {d.key: _score(first, dim_id(d.key)).score for d in rubric.dimensions}
        outcome = evaluate(rubric, dimension_levels=levels, stated=stated, met=met)
    except DecisionUnavailable as exc:
        match.status = MatchStatus.QUEUED
        match.error_code, match.error_message = exc.code, exc.message
        await session.commit()
        logger.warning("match_deferred", extra={"event": "match_deferred", **log})
        raise
    except AppError as exc:
        return await _fail(session, match, exc.code, exc.message, started, log)

    for key, value in outcome.dimensions.items():
        setattr(match, f"{key}_fit", value)
    match.must_have_fit = outcome.must_have
    match.overall_score = outcome.overall_score
    match.category = outcome.category
    match.hard_blocker = outcome.hard_blocker
    match.requirements = [
        {
            "key": r.key,
            "label": r.label,
            "status": r.status.value,
            "classification": r.classification.value,
            "stated_probability": r.stated_probability,
            "met_probability": r.met_probability,
        }
        for r in outcome.requirements
    ]
    match.matched_requirements = outcome.matched
    match.uncertain_requirements = outcome.partial
    match.missing_requirements = outcome.missing
    match.explanation = {
        "model": [first.model] + ([second.model] if second else []),
        "input_tokens": first.input_tokens + (second.input_tokens if second else 0),
        "state_chars": len(state),
        "truncated": truncated,
        "dimensions": {
            d.key: _explain_score(_score(first, dim_id(d.key))) for d in rubric.dimensions
        },
    }
    match.status = MatchStatus.DONE
    match.error_code = match.error_message = None
    match.completed_at = clock()
    match.duration_ms = round((time.monotonic() - started) * 1000)
    await session.commit()
    logger.info(
        "match_completed",
        extra={"event": "match_completed", "duration_ms": match.duration_ms, **log},
    )
    return match


def _score(result: DecisionResult, qid: str) -> ScoreAnswer:
    answer = result.answers[qid]
    assert isinstance(answer, ScoreAnswer)
    return answer


def _yes(result: DecisionResult | None, qid: str) -> float:
    assert result is not None
    answer = result.answers[qid]
    assert isinstance(answer, YesNoAnswer)
    return answer.noul


async def _fail(
    session: AsyncSession,
    match: MatchScore,
    code: str,
    message: str,
    started: float,
    log: dict[str, str],
) -> MatchScore:
    match.status = MatchStatus.FAILED
    match.error_code, match.error_message = code, message
    match.completed_at = utc_now()
    match.duration_ms = round((time.monotonic() - started) * 1000)
    await session.commit()
    logger.warning("match_failed", extra={"event": "match_failed", "code": code, **log})
    return match


async def mark_failed(session: AsyncSession, match_id: uuid.UUID, code: str, message: str) -> None:
    match = await session.get(MatchScore, match_id)
    if match is not None and match.status in (MatchStatus.QUEUED, MatchStatus.RUNNING):
        await _fail(session, match, code, message, time.monotonic(), {"match_id": str(match_id)})


# --- reading ----------------------------------------------------------------------------------


async def get_match(session: AsyncSession, match_id: uuid.UUID) -> MatchScore | None:
    return await session.get(MatchScore, match_id)


async def is_match_outdated(session: AsyncSession, match: MatchScore) -> bool:
    """Resume text, profile, job content or rubric changed since scoring (model revision is
    not checked here: that needs OpenJev online)."""
    job = await session.get(Job, match.job_id)
    resume = await session.get(Resume, match.resume_id)
    if job is None or resume is None:
        return False
    return (
        match.resume_text_hash != resume.text_hash
        or match.profile_hash != profile_hash(resume.profile)
        or match.job_content_hash != job.content_hash
        or match.rubric_version != CURRENT_RUBRIC.version
    )


async def list_matches(
    session: AsyncSession,
    *,
    job_id: uuid.UUID | None,
    resume_id: uuid.UUID | None,
    limit: int,
) -> list[MatchScore]:
    query = select(MatchScore).order_by(MatchScore.created_at.desc(), MatchScore.id).limit(limit)
    if job_id is not None:
        query = query.where(MatchScore.job_id == job_id)
    if resume_id is not None:
        query = query.where(MatchScore.resume_id == resume_id)
    return list((await session.execute(query)).scalars())
