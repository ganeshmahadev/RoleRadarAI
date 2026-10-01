"""Vacancy import: normalize → hash → deduplicate → store (PRD §25, §27).

Deterministic code only. Re-imports never silently overwrite stored content (PRD §15).
"""

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connectors.base import ExternalJob, NormalizedJob
from app.connectors.errors import SourceError
from app.connectors.registry import ConnectorRegistry
from app.models import Company, EuresStatus, Job, JobSource, SnapshotStatus, SourceType
from app.services.company_normalization import normalize_company_name, normalize_text
from app.services.eures_workflow import Clock, utc_now

logger = logging.getLogger(__name__)


class ImportOutcome(StrEnum):
    CREATED = "created"  # new canonical job
    ATTACHED_SOURCE = "attached_source"  # same vacancy found via another source
    UNCHANGED = "unchanged"  # this URL + content was already imported
    UPDATE_PENDING = "update_pending"  # known URL, changed content: awaiting review


@dataclass(frozen=True)
class ImportResult:
    job: Job
    outcome: ImportOutcome


class CompanyNotFound(LookupError):
    pass


class SnapshotConflict(ValueError):
    pass


def content_hash(job: NormalizedJob) -> str:
    canonical = {
        "title": normalize_text(job.title),
        "employer": normalize_text(job.employer_name or ""),
        "location": normalize_text(job.location or ""),
        "description": " ".join(job.description.split()),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def dedup_key(company_key: str, title: str, location: str | None, hash_: str) -> str:
    """normalized company + normalized title + location + content hash (PRD §27)."""
    parts = [company_key, normalize_text(title), normalize_text(location or ""), hash_]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _company_key(company: Company | None, job: NormalizedJob) -> str:
    if company is not None:
        return company.normalized_name
    return normalize_company_name(job.employer_name) if job.employer_name else ""


def _apply(job: Job, normalized: NormalizedJob) -> None:
    job.title = normalized.title
    job.normalized_title = normalize_text(normalized.title)
    job.employer_name = normalized.employer_name
    job.description = normalized.description
    job.location = normalized.location
    job.country = normalized.country
    job.city = normalized.city
    job.employment_type = normalized.employment_type
    job.workplace_type = normalized.workplace_type
    job.source_type = normalized.source_type
    job.source_url = normalized.source_url
    job.external_job_id = normalized.external_job_id
    job.apply_url = normalized.apply_url
    job.published_at = normalized.published_at
    job.expires_at = normalized.expires_at


def _from_snapshot(data: dict[str, Any]) -> NormalizedJob:
    values = dict(data)
    for key in ("published_at", "expires_at"):
        values[key] = datetime.fromisoformat(values[key]) if values.get(key) else None
    values["source_type"] = SourceType(values["source_type"])
    return NormalizedJob(**values)


async def _resolve_company(
    session: AsyncSession, company_id: uuid.UUID | None, employer_name: str | None
) -> Company | None:
    if company_id is not None:
        company = await session.get(Company, company_id)
        if company is None:
            raise CompanyNotFound("Company not found")
        return company
    if not employer_name:
        return None
    # Exact normalized-name match only; never a fuzzy guess (PRD §15).
    matches = (
        (
            await session.execute(
                select(Company).where(
                    Company.normalized_name == normalize_company_name(employer_name)
                )
            )
        )
        .scalars()
        .all()
    )
    return matches[0] if len(matches) == 1 else None


async def _find_similar(
    session: AsyncSession, company: Company | None, job: NormalizedJob, since: datetime
) -> Job | None:
    """Same company (linked, or same normalized employer name), title and location."""
    employer_key = normalize_company_name(job.employer_name) if job.employer_name else ""
    if company is None and not employer_key:
        return None  # never merge jobs whose employer is unknown
    location_key = normalize_text(job.location or "")
    candidates = (
        await session.execute(
            select(Job).where(
                Job.normalized_title == normalize_text(job.title), Job.created_at >= since
            )
        )
    ).scalars()
    for candidate in candidates:
        if normalize_text(candidate.location or "") != location_key:
            continue
        if company is not None and candidate.company_id == company.id:
            return candidate
        same_employer = bool(candidate.employer_name) and (
            normalize_company_name(candidate.employer_name or "") == employer_key
        )
        if company is None and candidate.company_id is None and same_employer:
            return candidate
    return None


async def store_normalized(
    session: AsyncSession,
    normalized: NormalizedJob,
    *,
    raw_payload: dict[str, Any] | None,
    company_id: uuid.UUID | None = None,
    similar_within_days: int | None = None,
    checked_by: str = "user",
    clock: Clock = utc_now,
) -> ImportResult:
    """`similar_within_days` (discovery only): attach the posting to an existing job with the
    same company, normalized title and location seen within that window, even when the
    description differs (the same vacancy on another board). The existing text is kept."""
    now = clock()
    hash_ = content_hash(normalized)
    explicit_company = await _resolve_company(session, company_id, None) if company_id else None

    snapshots = (
        (
            await session.execute(
                select(JobSource)
                .where(JobSource.source_url == normalized.source_url)
                .order_by(JobSource.fetched_at.desc())
            )
        )
        .scalars()
        .all()
    )

    if snapshots:
        same = next((s for s in snapshots if s.content_hash == hash_), None)
        if same is not None:
            same.fetched_at = now
            job = await session.get_one(Job, same.job_id)
            outcome = ImportOutcome.UNCHANGED
        else:
            job = await session.get_one(Job, snapshots[0].job_id)
            session.add(_snapshot(job, normalized, hash_, raw_payload, now, SnapshotStatus.PENDING))
            job.source_update_pending = True
            outcome = ImportOutcome.UPDATE_PENDING
    else:
        company = explicit_company or await _resolve_company(
            session, None, normalized.employer_name
        )
        key = dedup_key(
            _company_key(company, normalized), normalized.title, normalized.location, hash_
        )
        existing = await session.scalar(select(Job).where(Job.dedup_key == key))
        if existing is None and similar_within_days is not None:
            existing = await _find_similar(
                session, company, normalized, now - timedelta(days=similar_within_days)
            )
        if existing is not None:
            job = existing
            outcome = ImportOutcome.ATTACHED_SOURCE
        else:
            job = Job(content_hash=hash_, dedup_key=key, company_id=company.id if company else None)
            _apply(job, normalized)
            session.add(job)
            outcome = ImportOutcome.CREATED
        session.add(_snapshot(job, normalized, hash_, raw_payload, now, SnapshotStatus.ACCEPTED))

    if explicit_company is not None:
        if job.company_id is None:
            job.company_id = explicit_company.id
        # Importing from a company's EURES queue row completes that check (PRD §8).
        explicit_company.eures_status = EuresStatus.JOB_FOUND
        explicit_company.eures_last_checked_at = now
        explicit_company.eures_checked_by = checked_by

    await session.commit()
    return ImportResult(job=await load_job(session, job.id), outcome=outcome)


def _snapshot(
    job: Job,
    normalized: NormalizedJob,
    hash_: str,
    raw_payload: dict[str, Any] | None,
    now: datetime,
    status: SnapshotStatus,
) -> JobSource:
    return JobSource(
        job=job,
        source_type=normalized.source_type,
        source_url=normalized.source_url,
        final_url=normalized.final_url,
        external_job_id=normalized.external_job_id,
        content_hash=hash_,
        status=status,
        normalized=normalized.snapshot(),
        raw_payload=raw_payload,
        fetched_at=now,
    )


async def import_manual(
    session: AsyncSession,
    *,
    title: str,
    description: str,
    employer_name: str | None,
    location: str | None,
    source_url: str | None,
    apply_url: str | None,
    company_id: uuid.UUID | None,
    clock: Clock = utc_now,
) -> ImportResult:
    """Manual JD paste (PRD §26 priority 5). Text is stored as given; nothing is fetched."""
    draft = NormalizedJob(
        source_type=SourceType.MANUAL,
        source_url="",
        final_url="",
        title=" ".join(title.split()),
        description=description.strip(),
        employer_name=employer_name.strip() if employer_name and employer_name.strip() else None,
        location=location.strip() if location and location.strip() else None,
        apply_url=apply_url or source_url,
    )
    url = source_url or f"manual:{content_hash(draft)}"
    normalized = replace(draft, source_url=url, final_url=url)
    return await store_normalized(
        session, normalized, raw_payload=None, company_id=company_id, clock=clock
    )


async def import_from_url(
    session: AsyncSession,
    registry: ConnectorRegistry,
    url: str,
    *,
    company_id: uuid.UUID | None = None,
    clock: Clock = utc_now,
) -> ImportResult:
    started = time.monotonic()
    log = {"company_id": str(company_id) if company_id else None}
    logger.info("job_import_started", extra={"event": "job_import_started", **log})
    try:
        if company_id is not None and await session.get(Company, company_id) is None:
            raise CompanyNotFound("Company not found")
        connector = registry.select(url)
        external: ExternalJob = await connector.fetch_job_by_url(url)
        normalized = await connector.normalize_job(external)
        result = await store_normalized(
            session, normalized, raw_payload=external.payload, company_id=company_id, clock=clock
        )
    except (SourceError, CompanyNotFound) as exc:
        logger.info(
            "job_import_failed",
            extra={
                "event": "job_import_failed",
                "code": getattr(exc, "code", "COMPANY_NOT_FOUND"),
                "duration_ms": round((time.monotonic() - started) * 1000),
                **log,
            },
        )
        raise
    logger.info(
        "job_import_completed",
        extra={
            "event": "job_import_completed",
            "job_id": str(result.job.id),
            "outcome": result.outcome.value,
            "source_type": normalized.source_type.value,
            "duration_ms": round((time.monotonic() - started) * 1000),
            **log,
        },
    )
    return result


async def load_job(session: AsyncSession, job_id: uuid.UUID) -> Job:
    job = await session.scalar(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.sources))
        .execution_options(populate_existing=True)
    )
    if job is None:
        raise LookupError("Job not found")
    return job


async def review_snapshot(
    session: AsyncSession, job: Job, source_id: uuid.UUID, *, accept: bool
) -> Job:
    snapshot = next((s for s in job.sources if s.id == source_id), None)
    if snapshot is None or snapshot.status is not SnapshotStatus.PENDING:
        raise SnapshotConflict("This source update is not pending review")
    if accept:
        normalized = _from_snapshot(snapshot.normalized)
        company = await session.get(Company, job.company_id) if job.company_id else None
        key = dedup_key(
            _company_key(company, normalized),
            normalized.title,
            normalized.location,
            snapshot.content_hash,
        )
        clash = await session.scalar(select(Job.id).where(Job.dedup_key == key, Job.id != job.id))
        if clash is not None:
            raise SnapshotConflict("The updated content duplicates another stored job")
        _apply(job, replace(normalized, source_url=job.source_url or normalized.source_url))
        job.content_hash = snapshot.content_hash
        job.dedup_key = key
        snapshot.status = SnapshotStatus.ACCEPTED
    else:
        snapshot.status = SnapshotStatus.REJECTED
    job.source_update_pending = any(
        s.status is SnapshotStatus.PENDING for s in job.sources if s.id != snapshot.id
    )
    await session.commit()
    return await load_job(session, job.id)
