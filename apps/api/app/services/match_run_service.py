"""Batch scoring runs (PRD §28, §43–§44, §57, §65).

plan → create (QUEUED) → execute sequentially: per job, the cache is checked, irrelevant titles
are skipped, OpenJev outages are retried with bounded backoff, other failures fail only that job.
"""

import asyncio
import logging
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.matching.relevance import matching_role
from app.models import (
    MatchRun,
    MatchRunItem,
    MatchScore,
    MatchStatus,
    Resume,
    RunItemStatus,
    RunScope,
    RunStatus,
)
from app.providers.decision import DecisionProvider, DecisionUnavailable
from app.services import match_service
from app.services.eures_workflow import Clock, utc_now
from app.services.job_service import JobFilters, list_jobs

logger = logging.getLogger(__name__)

ACTIVE = (RunStatus.QUEUED, RunStatus.RUNNING)
FINISHED_ITEMS = (
    RunItemStatus.DONE,
    RunItemStatus.CACHED,
    RunItemStatus.SKIPPED,
    RunItemStatus.FAILED,
)
MAX_JOBS_PER_RUN = 500
Sleep = Callable[[float], Awaitable[None]]


class RunAlreadyActive(AppError):
    code = "RUN_ALREADY_ACTIVE"
    http_status = 409


class NothingToScore(AppError):
    code = "NOTHING_TO_SCORE"


class RunNotFound(AppError):
    code = "RUN_NOT_FOUND"
    http_status = 404


# --- planning ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class PlannedJob:
    job_id: uuid.UUID
    title: str
    matched_role: str | None  # None when the filter is off


@dataclass(frozen=True)
class RunPlan:
    resume_id: uuid.UUID
    scope: RunScope
    relevance_filter: bool  # effective: off when the profile has no target roles
    target_roles: list[str]
    to_score: list[PlannedJob]
    not_relevant: list[PlannedJob]


async def plan_run(
    session: AsyncSession,
    *,
    scope: RunScope,
    job_ids: Sequence[uuid.UUID] = (),
    apply_relevance_filter: bool = True,
) -> RunPlan:
    resume = await session.scalar(select(Resume).where(Resume.is_primary.is_(True)))
    if resume is None:
        raise match_service.NoPrimaryResume("Upload a resume first (Settings → Profile & resume)")
    rows, _, _ = await list_jobs(
        session, JobFilters(), sort="newest", page=1, page_size=MAX_JOBS_PER_RUN
    )
    if scope is RunScope.JOBS:
        wanted = set(job_ids)
        candidates = [r for r in rows if r.job.id in wanted]
    elif scope is RunScope.UNSCORED:
        candidates = [r for r in rows if r.match is None and not r.scoring]
    else:
        candidates = [r for r in rows if (r.match is None or r.match_outdated) and not r.scoring]

    roles = [r for r in resume.profile.target_roles if r.strip()]
    filtering = apply_relevance_filter and bool(roles)
    to_score: list[PlannedJob] = []
    not_relevant: list[PlannedJob] = []
    for row in reversed(candidates):  # oldest first
        role = matching_role(row.job.title, roles) if filtering else None
        planned = PlannedJob(row.job.id, row.job.title, role)
        (to_score if role or not filtering else not_relevant).append(planned)
    return RunPlan(resume.id, scope, filtering, roles, to_score, not_relevant)


async def create_run(session: AsyncSession, plan: RunPlan) -> MatchRun:
    active = await session.scalar(select(MatchRun).where(MatchRun.status.in_(ACTIVE)))
    if active is not None:
        raise RunAlreadyActive("A batch run is already in progress; wait for it or cancel it")
    if not plan.to_score:
        raise NothingToScore("No jobs to score with these settings")
    run = MatchRun(
        resume_id=plan.resume_id,
        status=RunStatus.QUEUED,
        scope=plan.scope,
        relevance_filter=plan.relevance_filter,
        target_roles=plan.target_roles,
    )
    position = 0
    for job in plan.to_score:
        run.items.append(
            MatchRunItem(
                job_id=job.job_id,
                position=position,
                job_title=job.title,
                matched_role=job.matched_role,
            )
        )
        position += 1
    for job in plan.not_relevant:
        run.items.append(
            MatchRunItem(
                job_id=job.job_id,
                position=position,
                job_title=job.title,
                status=RunItemStatus.SKIPPED,
                reason="Title does not match any of your target roles",
            )
        )
        position += 1
    session.add(run)
    await session.commit()
    logger.info("match_run_created", extra={"event": "match_run_created", "run_id": str(run.id)})
    return run


# --- execution --------------------------------------------------------------------------------


async def _score_with_retries(
    session: AsyncSession,
    provider: DecisionProvider,
    match_id: uuid.UUID,
    delays: Sequence[float],
    sleep: Sleep,
    clock: Clock,
) -> MatchScore | None:
    """Retry only provider outages, with bounded exponential backoff (P7-004)."""
    for attempt in range(len(delays) + 1):
        try:
            return await match_service.run_match(session, provider, match_id, clock=clock)
        except DecisionUnavailable as exc:
            if attempt == len(delays):
                await match_service.mark_failed(session, match_id, exc.code, exc.message)
                raise
            logger.info(
                "match_retry_scheduled",
                extra={
                    "event": "match_retry_scheduled",
                    "match_id": str(match_id),
                    "delay": delays[attempt],
                },
            )
            await sleep(delays[attempt])
    return None  # unreachable


async def _wait_for(session: AsyncSession, match: MatchScore, sleep: Sleep) -> MatchScore:
    """Another request is already scoring this exact input: wait for it instead of duplicating."""
    for _ in range(720):  # ≤ 1 h at 5 s
        await session.refresh(match)
        if match.status not in (MatchStatus.QUEUED, MatchStatus.RUNNING):
            break
        await sleep(5)
    return match


def _finish(
    item: MatchRunItem,
    status: RunItemStatus,
    clock: Clock,
    *,
    reason: str | None = None,
    code: str | None = None,
) -> None:
    item.status, item.reason, item.error_code = status, reason, code
    item.completed_at = clock()


async def execute_run(
    session: AsyncSession,
    provider: DecisionProvider,
    run_id: uuid.UUID,
    *,
    delays: Sequence[float],
    sleep: Sleep = asyncio.sleep,
    clock: Clock = utc_now,
) -> MatchRun | None:
    run = await session.get(MatchRun, run_id)
    if run is None or run.status is not RunStatus.QUEUED:
        return run
    run.status, run.started_at = RunStatus.RUNNING, clock()
    await session.commit()
    log = {"run_id": str(run.id)}
    logger.info("match_run_started", extra={"event": "match_run_started", **log})

    pending = [i for i in run.items if i.status is RunItemStatus.PENDING]
    for index, item in enumerate(pending):
        await session.refresh(run, ["status"])
        if run.status is RunStatus.CANCELLED:
            for rest in pending[index:]:
                _finish(rest, RunItemStatus.SKIPPED, clock, reason="Run cancelled")
            break
        item.status, item.started_at = RunItemStatus.RUNNING, clock()
        run.current_job_id = item.job_id
        await session.commit()
        try:
            match, created = await match_service.request_score(
                session, provider, job_id=item.job_id, resume_id=run.resume_id
            )
            item.match_id = match.id
            if not created and match.status is MatchStatus.DONE:
                _finish(item, RunItemStatus.CACHED, clock)
            else:
                if created:
                    result = await _score_with_retries(
                        session, provider, match.id, delays, sleep, clock
                    )
                else:
                    result = await _wait_for(session, match, sleep)
                if result is not None and result.status is MatchStatus.DONE:
                    _finish(item, RunItemStatus.DONE, clock)
                else:
                    code = result.error_code if result else None
                    message = result.error_message if result else "Scoring did not finish"
                    _finish(item, RunItemStatus.FAILED, clock, reason=message, code=code)
        except DecisionUnavailable as exc:
            # OpenJev stayed down after the retries: stop instead of failing every remaining job.
            _finish(item, RunItemStatus.FAILED, clock, reason=exc.message, code=exc.code)
            for rest in pending[index + 1 :]:
                _finish(
                    rest, RunItemStatus.SKIPPED, clock, reason="Run stopped: OpenJev unavailable"
                )
            run.status, run.error_code, run.error_message = RunStatus.FAILED, exc.code, exc.message
            break
        except AppError as exc:  # e.g. the job was deleted meanwhile: only this job fails
            _finish(item, RunItemStatus.FAILED, clock, reason=exc.message, code=exc.code)
        await session.commit()
        logger.info(
            "match_run_item_finished",
            extra={
                "event": "match_run_item_finished",
                "job_id": str(item.job_id),
                "status": item.status.value,
                **log,
            },
        )

    if run.status is RunStatus.RUNNING:
        run.status = RunStatus.DONE
    run.current_job_id = None
    run.completed_at = clock()
    await session.commit()
    logger.info(
        "match_run_finished",
        extra={"event": "match_run_finished", "status": run.status.value, **log},
    )
    return run


async def fail_run(session: AsyncSession, run_id: uuid.UUID, code: str, message: str) -> None:
    run = await session.get(MatchRun, run_id)
    if run is None or run.status not in ACTIVE:
        return
    for item in run.items:
        if item.status in (RunItemStatus.PENDING, RunItemStatus.RUNNING):
            _finish(item, RunItemStatus.SKIPPED, utc_now, reason=message)
    run.status, run.error_code, run.error_message = RunStatus.FAILED, code, message
    run.completed_at = utc_now()
    await session.commit()


async def cancel_run(session: AsyncSession, run: MatchRun) -> MatchRun:
    """QUEUED runs stop at once; a RUNNING run stops after its current job."""
    if run.status is RunStatus.QUEUED:
        for item in run.items:
            if item.status is RunItemStatus.PENDING:
                _finish(item, RunItemStatus.SKIPPED, utc_now, reason="Run cancelled")
        run.completed_at = utc_now()
    if run.status in ACTIVE:
        run.status = RunStatus.CANCELLED
        await session.commit()
    return run


# --- reading ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunProgress:
    counts: dict[str, int]
    finished: int
    total: int
    seconds_per_job: float | None
    seconds_remaining: float | None


async def average_scoring_seconds(session: AsyncSession, sample: int = 20) -> float | None:
    recent = (
        select(MatchScore.duration_ms)
        .where(MatchScore.status == MatchStatus.DONE, MatchScore.duration_ms.is_not(None))
        .order_by(MatchScore.completed_at.desc())
        .limit(sample)
        .subquery()
    )
    value = await session.scalar(select(func.avg(recent.c.duration_ms)))
    return float(value) / 1000 if value is not None else None


async def progress(session: AsyncSession, run: MatchRun) -> RunProgress:
    counts = Counter(item.status.value for item in run.items)
    total = len(run.items)
    finished = sum(counts[s.value] for s in FINISHED_ITEMS)
    to_go = counts[RunItemStatus.PENDING.value] + counts[RunItemStatus.RUNNING.value]
    per_job = await average_scoring_seconds(session)
    remaining = per_job * to_go if per_job is not None and run.status in ACTIVE else None
    return RunProgress(
        counts={s.value: counts[s.value] for s in RunItemStatus},
        finished=finished,
        total=total,
        seconds_per_job=per_job,
        seconds_remaining=remaining,
    )


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> MatchRun:
    run = await session.get(MatchRun, run_id, populate_existing=True)
    if run is None:
        raise RunNotFound("Batch run not found")
    return run


async def list_runs(session: AsyncSession, *, limit: int) -> list[MatchRun]:
    rows = await session.execute(select(MatchRun).order_by(MatchRun.created_at.desc()).limit(limit))
    return list(rows.scalars())
