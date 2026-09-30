import uuid
from dataclasses import dataclass, field

from sqlalchemy import ColumnElement, Select, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, EuresStatus
from app.schemas.company import CompanySort
from app.services.company_normalization import normalize_company_name

# "Checked" means the EURES review reached an outcome (PRD §8).
UNCHECKED_STATUSES = (EuresStatus.NOT_CHECKED, EuresStatus.OPENED)


@dataclass(frozen=True)
class CompanyFilters:
    q: str | None = None
    eures_status: list[EuresStatus] = field(default_factory=list)
    checked: bool | None = None
    siri_certified: bool | None = None


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _conditions(filters: CompanyFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.q and filters.q.strip():
        raw = filters.q.strip()
        term = f"%{_escape_like(raw)}%"
        options: list[ColumnElement[bool]] = [
            Company.company_name.ilike(term, escape="\\"),
            Company.cvr.startswith(raw, autoescape=True),
        ]
        normalized = normalize_company_name(raw)
        if normalized:
            options.append(
                Company.normalized_name.like(f"%{_escape_like(normalized)}%", escape="\\")
            )
        conditions.append(or_(*options))
    if filters.eures_status:
        conditions.append(Company.eures_status.in_(filters.eures_status))
    if filters.checked is True:
        conditions.append(Company.eures_status.not_in(UNCHECKED_STATUSES))
    elif filters.checked is False:
        conditions.append(Company.eures_status.in_(UNCHECKED_STATUSES))
    if filters.siri_certified is not None:
        conditions.append(Company.siri_certified.is_(filters.siri_certified))
    return conditions or [~false()]


def _ordered(query: Select[Company], sort: CompanySort) -> Select[Company]:
    if sort == "name":
        return query.order_by(func.lower(Company.company_name), Company.cvr)
    if sort == "last_checked":
        return query.order_by(Company.eures_last_checked_at.desc().nulls_last(), Company.cvr)
    return query.order_by(Company.source_position.asc().nulls_last(), Company.cvr)


async def list_companies(
    session: AsyncSession,
    filters: CompanyFilters,
    *,
    page: int,
    page_size: int,
    sort: CompanySort = "position",
) -> tuple[list[Company], int]:
    conditions = _conditions(filters)
    total = await session.scalar(select(func.count()).select_from(Company).where(*conditions))
    query = _ordered(select(Company).where(*conditions), sort)
    rows = await session.execute(query.offset((page - 1) * page_size).limit(page_size))
    return list(rows.scalars()), total or 0


async def get_company(session: AsyncSession, company_id: uuid.UUID) -> Company | None:
    return await session.get(Company, company_id)
