import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, EuresStatus


def make_company(cvr: str, name: str = "Example A/S") -> Company:
    return Company(
        company_name=name,
        normalized_name="example",
        cvr=cvr,
        eures_search_url="https://europa.eu/eures/portal/jv-se/search?keywordsEverywhere=Example",
    )


async def test_defaults(session: AsyncSession) -> None:
    session.add(make_company("12345678"))
    await session.commit()
    company = (await session.execute(select(Company))).scalar_one()
    assert company.eures_status is EuresStatus.NOT_CHECKED
    assert company.siri_certified is True
    assert company.active is True
    assert company.created_at is not None


@pytest.mark.parametrize("cvr", ["00012345", "8485085", "423380281", "DK-12345678"])
async def test_cvr_is_preserved_exactly(session: AsyncSession, cvr: str) -> None:
    session.add(make_company(cvr))
    await session.commit()
    stored = (await session.execute(select(Company.cvr))).scalar_one()
    assert stored == cvr
    assert isinstance(stored, str)


async def test_cvr_is_unique(session: AsyncSession) -> None:
    session.add_all([make_company("12345678", "A A/S"), make_company("12345678", "B A/S")])
    with pytest.raises(IntegrityError, match="uq_companies_cvr"):
        await session.commit()


async def test_database_rejects_unknown_eures_status(session: AsyncSession) -> None:
    session.add(make_company("12345678"))
    await session.commit()
    with pytest.raises(IntegrityError, match="ck_companies_eures_status"):
        await session.execute(text("UPDATE companies SET eures_status = 'Pending'"))
