"""Job listing with each job's current Match (PRD §31, §21; P6 decisions in BACKLOG).

A job's Match is its latest DONE match for the primary resume. Ranking puts blocked jobs below
unblocked ones by default (OD-3) and unscored jobs last.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import ColumnElement, and_, exists, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.matching.rubric import CURRENT_RUBRIC
from app.models import Company, Job, JobStatus, MatchScore, MatchStatus, Resume, SourceType
from app.services.company_service import escape_like
from app.services.match_service import profile_hash

JobSort = Literal["match", "newest", "company", "title"]
BlockedMode = Literal["last", "mixed", "exclude"]
DEFAULT_STATUSES = (JobStatus.NEW, JobStatus.SAVED)  # ignored jobs only on request


@dataclass(frozen=True)
class JobFilters:
    q: str | None = None  # title or employer
    location: str | None = None  # location, city or country
    company_id: uuid.UUID | None = None
    source_type: SourceType | None = None
    siri_only: bool = False
    statuses: tuple[JobStatus, ...] = DEFAULT_STATUSES
    scored: bool | None = None
    min_score: float | None = None
    blocked: BlockedMode = "last"
    update_pending: bool | None = None
    category: str | None = None  # stored band, e.g. STRONG (never re-derived from the score)


@dataclass(frozen=True)
class JobRow:
    job: Job
    match: MatchScore | None
    scoring: bool  # a newer score is queued or running
    match_outdated: bool


@dataclass(frozen=True)
class PrimaryContext:
    resume_id: uuid.UUID
    text_hash: str
    profile_hash: str


async def primary_context(session: AsyncSession) -> PrimaryContext | None:
    resume = await session.scalar(select(Resume).where(Resume.is_primary.is_(True)))
    if resume is None:
        return None
    return PrimaryContext(resume.id, resume.text_hash, profile_hash(resume.profile))


def is_outdated(match: MatchScore, job: Job, ctx: PrimaryContext | None) -> bool:
    """Inputs changed since scoring (the model revision is not checked offline)."""
    if ctx is None or match.resume_id != ctx.resume_id:
        return False
    return (
        match.resume_text_hash != ctx.text_hash
        or match.profile_hash != ctx.profile_hash
        or match.job_content_hash != job.content_hash
        or match.rubric_version != CURRENT_RUBRIC.version
    )


async def list_jobs(
    session: AsyncSession,
    filters: JobFilters,
    *,
    sort: JobSort,
    page: int,
    page_size: int,
) -> tuple[list[JobRow], int, PrimaryContext | None]:
    ctx = await primary_context(session)
    resume_id = ctx.resume_id if ctx else uuid.UUID(int=0)

    latest_done = (
        select(MatchScore)
        .where(MatchScore.resume_id == resume_id, MatchScore.status == MatchStatus.DONE)
        .ext(distinct_on(MatchScore.job_id))
        .order_by(MatchScore.job_id, MatchScore.created_at.desc())
        .subquery()
    )
    match = aliased(MatchScore, latest_done)
    company = aliased(Company)
    scoring = exists().where(
        MatchScore.job_id == Job.id,
        MatchScore.resume_id == resume_id,
        MatchScore.status.in_((MatchStatus.QUEUED, MatchStatus.RUNNING)),
    )

    conditions: list[ColumnElement[bool]] = [Job.status.in_(filters.statuses)]
    if filters.q and filters.q.strip():
        term = f"%{escape_like(filters.q.strip())}%"
        conditions.append(
            or_(
                Job.title.ilike(term, escape="\\"),
                Job.employer_name.ilike(term, escape="\\"),
                company.company_name.ilike(term, escape="\\"),
            )
        )
    if filters.location and filters.location.strip():
        term = f"%{escape_like(filters.location.strip())}%"
        conditions.append(
            or_(
                Job.location.ilike(term, escape="\\"),
                Job.city.ilike(term, escape="\\"),
                Job.country.ilike(term, escape="\\"),
            )
        )
    if filters.company_id is not None:
        conditions.append(Job.company_id == filters.company_id)
    if filters.source_type is not None:
        conditions.append(Job.source_type == filters.source_type)
    if filters.siri_only:
        conditions.append(company.siri_certified.is_(True))
    if filters.scored is True:
        conditions.append(match.id.is_not(None))
    elif filters.scored is False:
        conditions.append(match.id.is_(None))
    if filters.min_score is not None:
        conditions.append(match.overall_score >= filters.min_score)
    if filters.blocked == "exclude":
        conditions.append(or_(match.id.is_(None), match.hard_blocker.is_(False)))
    if filters.category is not None:
        conditions.append(match.category == filters.category)
    if filters.update_pending is not None:
        conditions.append(Job.source_update_pending.is_(filters.update_pending))

    base = (
        select(Job, match, scoring.label("scoring"))
        .outerjoin(latest_done, latest_done.c.job_id == Job.id)
        .outerjoin(company, company.id == Job.company_id)
        .where(and_(*conditions))
    )

    order: list[ColumnElement[Any]]
    if sort == "match":
        order = [match.id.is_(None)]  # unscored last
        if filters.blocked == "last":
            order.append(match.hard_blocker.is_(True))
        order += [match.overall_score.desc().nulls_last(), Job.created_at.desc()]
    elif sort == "company":
        order = [
            func.lower(func.coalesce(company.company_name, Job.employer_name)).asc().nulls_last(),
            Job.created_at.desc(),
        ]
    elif sort == "title":
        order = [func.lower(Job.title).asc(), Job.created_at.desc()]
    else:
        order = [Job.created_at.desc()]

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = await session.execute(
        base.order_by(*order, Job.id).offset((page - 1) * page_size).limit(page_size)
    )
    items = [
        JobRow(
            job=job,
            match=m,
            scoring=bool(active),
            match_outdated=bool(m and is_outdated(m, job, ctx)),
        )
        for job, m, active in rows
    ]
    return items, total or 0, ctx


async def set_status(session: AsyncSession, job: Job, status: JobStatus) -> Job:
    job.status = status
    await session.commit()
    return job
