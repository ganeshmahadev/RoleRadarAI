import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient, QueryParams
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EuresStatus
from tests.factories import create_company


@pytest.fixture
async def companies(session: AsyncSession) -> None:
    await create_company(session, "3Shape A/S", "25553489", position=2)
    await create_company(session, "&TRADITION A/S", "18169304", position=1)
    await create_company(
        session,
        "A.P. MØLLER HOLDING A/S",
        "00012345",
        position=3,
        status=EuresStatus.CHECKED_NO_JOBS,
        last_checked_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
    await create_company(
        session, "Aalborg Håndbold A/S", "8485085", position=4, status=EuresStatus.OPENED
    )
    await create_company(session, "Old Co ApS", "423380281", position=5, siri_certified=False)


def names(body: dict[str, list[dict[str, str]]]) -> list[str]:
    return [item["company_name"] for item in body["items"]]


@pytest.mark.usefixtures("companies")
async def test_lists_in_siri_order_with_pagination(client: AsyncClient) -> None:
    response = await client.get("/api/v1/companies", params={"page_size": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert (body["page"], body["page_size"]) == (1, 2)
    assert names(body) == ["&TRADITION A/S", "3Shape A/S"]

    page3 = (await client.get("/api/v1/companies", params={"page_size": 2, "page": 3})).json()
    assert names(page3) == ["Old Co ApS"]


@pytest.mark.usefixtures("companies")
async def test_cvr_is_returned_as_text(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/companies", params={"q": "00012345"})).json()
    assert [item["cvr"] for item in body["items"]] == ["00012345"]


@pytest.mark.usefixtures("companies")
@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("3shape", ["3Shape A/S"]),
        ("møller", ["A.P. MØLLER HOLDING A/S"]),
        ("a.p. møller", ["A.P. MØLLER HOLDING A/S"]),
        ("handbold", ["Aalborg Håndbold A/S"]),
        ("2555", ["3Shape A/S"]),
        ("&trad", ["&TRADITION A/S"]),
        ("100%", []),
        ("nothing-matches", []),
    ],
)
async def test_search(client: AsyncClient, q: str, expected: list[str]) -> None:
    body = (await client.get("/api/v1/companies", params={"q": q})).json()
    assert names(body) == expected


@pytest.mark.usefixtures("companies")
async def test_filters(client: AsyncClient) -> None:
    async def get(**params: str | list[str]) -> list[str]:
        return names((await client.get("/api/v1/companies", params=QueryParams(params))).json())

    assert await get(eures_status="OPENED") == ["Aalborg Håndbold A/S"]
    assert await get(eures_status=["OPENED", "CHECKED_NO_JOBS"]) == [
        "A.P. MØLLER HOLDING A/S",
        "Aalborg Håndbold A/S",
    ]
    assert await get(checked="true") == ["A.P. MØLLER HOLDING A/S"]
    assert len(await get(checked="false")) == 4
    assert await get(siri_certified="false") == ["Old Co ApS"]
    assert await get(sort="name") == [
        "&TRADITION A/S",
        "3Shape A/S",
        "A.P. MØLLER HOLDING A/S",
        "Aalborg Håndbold A/S",
        "Old Co ApS",
    ]
    assert (await get(sort="last_checked"))[0] == "A.P. MØLLER HOLDING A/S"


@pytest.mark.parametrize(
    "params",
    [{"eures_status": "Pending"}, {"page": "0"}, {"page_size": "201"}, {"sort": "random"}],
)
async def test_rejects_invalid_parameters(client: AsyncClient, params: dict[str, str]) -> None:
    assert (await client.get("/api/v1/companies", params=params)).status_code == 422


async def test_company_detail(client: AsyncClient, session: AsyncSession) -> None:
    company = await create_company(session, "3Shape A/S", "25553489", position=2)
    response = await client.get(f"/api/v1/companies/{company.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["cvr"] == "25553489"
    assert body["eures_status"] == "NOT_CHECKED"
    assert body["eures_search_url"].endswith(
        "keywordsEverywhere=3Shape+A%2FS"
        "&publicationPeriod=LAST_MONTH&previousPageType=findJob&lang=en"
    )


async def test_company_detail_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/companies/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Company not found"}
    assert (await client.get("/api/v1/companies/not-a-uuid")).status_code == 422
