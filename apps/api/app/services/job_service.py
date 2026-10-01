import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job
from app.services.company_service import escape_like


async def list_jobs(
    session: AsyncSession,
    *,
    company_id: uuid.UUID | None,
    q: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Job], int]:
    conditions = []
    if company_id is not None:
        conditions.append(Job.company_id == company_id)
    if q and q.strip():
        term = f"%{escape_like(q.strip())}%"
        conditions.append(
            or_(
                Job.title.ilike(term, escape="\\"),
                Job.employer_name.ilike(term, escape="\\"),
                Job.location.ilike(term, escape="\\"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(Job).where(*conditions))
    rows = await session.execute(
        select(Job)
        .where(*conditions)
        .order_by(Job.created_at.desc(), Job.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars()), total or 0
