from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, EuresStatus
from app.services.company_normalization import build_eures_search_url, normalize_company_name


async def create_company(
    session: AsyncSession,
    name: str,
    cvr: str,
    *,
    position: int | None = None,
    status: EuresStatus = EuresStatus.NOT_CHECKED,
    last_checked_at: datetime | None = None,
    siri_certified: bool = True,
    notes: str | None = None,
) -> Company:
    company = Company(
        company_name=name,
        normalized_name=normalize_company_name(name),
        cvr=cvr,
        source_position=position,
        siri_certified=siri_certified,
        eures_search_url=build_eures_search_url(name),
        eures_status=status,
        eures_last_checked_at=last_checked_at,
        eures_notes=notes,
    )
    session.add(company)
    await session.commit()
    return company
