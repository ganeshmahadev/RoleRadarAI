import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, EuresStatus
from app.services import eures_workflow
from tests.factories import create_company

CHECKED_AT = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


async def post(client: AsyncClient, company: Company, action: str) -> dict[str, object]:
    response = await client.post(f"/api/v1/companies/{company.id}/{action}")
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


# --- transitions (PRD §8 table) -----------------------------------------------------------


async def test_open_marks_not_checked_as_opened(client: AsyncClient, session: AsyncSession) -> None:
    company = await create_company(session, "3Shape A/S", "25553489", position=1)
    body = await post(client, company, "eures-opened")
    assert body["eures_status"] == "OPENED"
    assert body["eures_last_checked_at"] is None


@pytest.mark.parametrize(
    "status", [EuresStatus.CHECKED_NO_JOBS, EuresStatus.JOB_FOUND, EuresStatus.ERROR]
)
async def test_open_never_downgrades(
    client: AsyncClient, session: AsyncSession, status: EuresStatus
) -> None:
    company = await create_company(
        session, "3Shape A/S", "25553489", status=status, last_checked_at=CHECKED_AT
    )
    body = await post(client, company, "eures-opened")
    assert body["eures_status"] == status.value
    assert body["eures_last_checked_at"] == "2026-10-01T08:00:00Z"


@pytest.mark.parametrize(
    ("action", "expected"),
    [("mark-no-jobs", "CHECKED_NO_JOBS"), ("mark-eures-error", "ERROR")],
)
async def test_completing_actions_set_status_and_timestamp(
    client: AsyncClient, session: AsyncSession, action: str, expected: str
) -> None:
    company = await create_company(session, "3Shape A/S", "25553489", status=EuresStatus.OPENED)
    before = datetime.now(UTC)
    body = await post(client, company, action)
    assert body["eures_status"] == expected
    assert isinstance(body["eures_last_checked_at"], str)
    assert datetime.fromisoformat(body["eures_last_checked_at"]) >= before


async def test_reset_clears_status_and_timestamp(
    client: AsyncClient, session: AsyncSession
) -> None:
    company = await create_company(
        session,
        "3Shape A/S",
        "25553489",
        status=EuresStatus.CHECKED_NO_JOBS,
        last_checked_at=CHECKED_AT,
        notes="keep me",
    )
    body = await post(client, company, "reset-eures")
    assert body["eures_status"] == "NOT_CHECKED"
    assert body["eures_last_checked_at"] is None
    assert body["eures_notes"] == "keep me"


async def test_service_uses_injected_clock(session: AsyncSession) -> None:
    company = await create_company(session, "3Shape A/S", "25553489")
    await eures_workflow.mark_no_relevant_jobs(session, company, clock=lambda: CHECKED_AT)
    assert company.eures_last_checked_at == CHECKED_AT


# --- notes --------------------------------------------------------------------------------


async def test_notes_update_and_clear(client: AsyncClient, session: AsyncSession) -> None:
    company = await create_company(session, "3Shape A/S", "25553489", status=EuresStatus.OPENED)
    url = f"/api/v1/companies/{company.id}"

    body = (await client.patch(url, json={"eures_notes": "  Only sales roles  "})).json()
    assert body["eures_notes"] == "Only sales roles"
    assert body["eures_status"] == "OPENED"

    assert (await client.patch(url, json={})).json()["eures_notes"] == "Only sales roles"
    assert (await client.patch(url, json={"eures_notes": "  "})).json()["eures_notes"] is None


async def test_notes_length_limit_and_unknown_company(client: AsyncClient) -> None:
    missing = f"/api/v1/companies/{uuid.uuid4()}"
    assert (await client.patch(missing, json={"eures_notes": "x"})).status_code == 404
    assert (await client.post(f"{missing}/mark-no-jobs")).status_code == 404


async def test_notes_too_long_rejected(client: AsyncClient, session: AsyncSession) -> None:
    company = await create_company(session, "3Shape A/S", "25553489")
    response = await client.patch(
        f"/api/v1/companies/{company.id}", json={"eures_notes": "x" * 5001}
    )
    assert response.status_code == 422


async def test_status_cannot_be_patched_directly(
    client: AsyncClient, session: AsyncSession
) -> None:
    company = await create_company(session, "3Shape A/S", "25553489")
    body = (
        await client.patch(f"/api/v1/companies/{company.id}", json={"eures_status": "JOB_FOUND"})
    ).json()
    assert body["eures_status"] == "NOT_CHECKED"


# --- EURES search, next unchecked, stats --------------------------------------------------


async def test_eures_search(client: AsyncClient, session: AsyncSession) -> None:
    company = await create_company(session, "3Shape A/S", "25553489")
    body = (await client.get(f"/api/v1/companies/{company.id}/eures-search")).json()
    assert body == {
        "company_id": str(company.id),
        "company_name": "3Shape A/S",
        "url": company.eures_search_url,
        "status": "NOT_CHECKED",
    }


@pytest.fixture
async def queue(session: AsyncSession) -> list[Company]:
    return [
        await create_company(session, "A A/S", "1", position=1, status=EuresStatus.CHECKED_NO_JOBS),
        await create_company(session, "B A/S", "2", position=2),
        await create_company(session, "C A/S", "3", position=3, status=EuresStatus.JOB_FOUND),
        await create_company(session, "D A/S", "4", position=4, status=EuresStatus.OPENED),
        await create_company(session, "E A/S", "5", position=5, status=EuresStatus.ERROR),
    ]


async def test_next_unchecked(client: AsyncClient, queue: list[Company]) -> None:
    async def next_name(**params: int) -> str:
        response = await client.get("/api/v1/eures/next-unchecked", params=params)
        assert response.status_code == 200
        name: str = response.json()["company_name"]
        return name

    assert await next_name() == "B A/S"
    assert await next_name(after_position=2) == "D A/S"  # OPENED still counts as unchecked
    assert await next_name(after_position=4) == "B A/S"  # wraps around


async def test_next_unchecked_when_done(client: AsyncClient, session: AsyncSession) -> None:
    await create_company(session, "A A/S", "1", position=1, status=EuresStatus.CHECKED_NO_JOBS)
    response = await client.get("/api/v1/eures/next-unchecked")
    assert response.status_code == 404
    assert response.json() == {"detail": "All companies have been checked"}


@pytest.mark.usefixtures("queue")
async def test_queue_stats(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/eures/stats")).json()
    assert body == {
        "total": 5,
        "checked": 3,
        "remaining": 2,
        "by_status": {
            "NOT_CHECKED": 1,
            "OPENED": 1,
            "CHECKED_NO_JOBS": 1,
            "JOB_FOUND": 1,
            "ERROR": 1,
        },
    }


async def test_queue_stats_empty(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/eures/stats")).json()
    assert (body["total"], body["checked"], body["remaining"]) == (0, 0, 0)
