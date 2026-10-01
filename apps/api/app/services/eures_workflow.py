"""EURES discovery workflow (PRD §8).

RoleRadarAI never fetches EURES content. These functions only record the human
workflow state for each company.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, EuresStatus
from app.services.company_service import UNCHECKED_STATUSES

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class QueueStats:
    total: int
    checked: int
    remaining: int
    by_status: dict[EuresStatus, int]


async def _save(session: AsyncSession, company: Company, event: str) -> Company:
    await session.commit()
    await session.refresh(company)
    logger.info(
        event,
        extra={"event": event, "company_id": str(company.id), "status": company.eures_status},
    )
    return company


async def mark_opened(session: AsyncSession, company: Company) -> Company:
    """Opening the search never downgrades a completed status."""
    if company.eures_status is EuresStatus.NOT_CHECKED:
        company.eures_status = EuresStatus.OPENED
    return await _save(session, company, "eures_opened")


async def _complete(
    session: AsyncSession, company: Company, status: EuresStatus, event: str, clock: Clock
) -> Company:
    company.eures_status = status
    company.eures_last_checked_at = clock()
    company.eures_checked_by = "user"
    return await _save(session, company, event)


async def mark_no_relevant_jobs(
    session: AsyncSession, company: Company, clock: Clock = utc_now
) -> Company:
    return await _complete(
        session, company, EuresStatus.CHECKED_NO_JOBS, "eures_no_relevant_jobs", clock
    )


async def mark_error(session: AsyncSession, company: Company, clock: Clock = utc_now) -> Company:
    return await _complete(session, company, EuresStatus.ERROR, "eures_error", clock)


async def reset(session: AsyncSession, company: Company) -> Company:
    company.eures_status = EuresStatus.NOT_CHECKED
    company.eures_last_checked_at = None
    company.eures_checked_by = None
    return await _save(session, company, "eures_reset")


async def update_notes(session: AsyncSession, company: Company, notes: str | None) -> Company:
    cleaned = notes.strip() if notes else None
    company.eures_notes = cleaned or None
    return await _save(session, company, "eures_notes_updated")


async def next_unchecked(
    session: AsyncSession, after_position: int | None = None
) -> Company | None:
    """Next NOT_CHECKED/OPENED company in SIRI list order, optionally after a position.

    Wraps around to the start of the list when nothing remains after `after_position`.
    """
    base = select(Company).where(
        Company.eures_status.in_(UNCHECKED_STATUSES), Company.source_position.is_not(None)
    )
    order = (Company.source_position.asc(), Company.cvr)
    if after_position is not None:
        found = await session.scalar(
            base.where(Company.source_position > after_position).order_by(*order).limit(1)
        )
        if found is not None:
            return found
    return await session.scalar(base.order_by(*order).limit(1))


async def queue_stats(session: AsyncSession) -> QueueStats:
    rows = await session.execute(
        select(Company.eures_status, func.count()).group_by(Company.eures_status)
    )
    by_status = dict.fromkeys(EuresStatus, 0)
    for status, count in rows:
        by_status[status] = count
    total = sum(by_status.values())
    remaining = sum(by_status[s] for s in UNCHECKED_STATUSES)
    return QueueStats(
        total=total, checked=total - remaining, remaining=remaining, by_status=by_status
    )
