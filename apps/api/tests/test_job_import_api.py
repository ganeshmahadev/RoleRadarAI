import json
from collections.abc import Callable, Iterator

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.factory import build_registry, get_registry
from app.main import create_app
from app.models import Company, EuresStatus, Job, JobSource
from tests.factories import create_company
from tests.fetch_helpers import fetcher, fixture, html_response

GH_URL = "https://job-boards.greenhouse.io/examplefintech/jobs/7001001"
GH_API = "boards-api.greenhouse.io/v1/boards/examplefintech/jobs/7001001"
PAGE_URL = "https://careers.example.com/jobs/1042"


class Web:
    """Mutable fake internet keyed by Host+path (requests arrive at pinned IPs)."""

    def __init__(self) -> None:
        self.routes: dict[str, Callable[[], httpx.Response]] = {}

    def set(self, key: str, response: Callable[[], httpx.Response]) -> None:
        self.routes[key] = response

    def handler(self, request: httpx.Request) -> httpx.Response:
        key = f"{request.headers['host']}{request.url.raw_path.decode()}"
        return self.routes.get(key, lambda: httpx.Response(404))()


@pytest.fixture
def web() -> Web:
    w = Web()
    w.set(GH_API, lambda: httpx.Response(200, text=fixture("greenhouse_job.json")))
    w.set("careers.example.com/jobs/1042", lambda: html_response(fixture("jsonld_basic.html")))
    return w


@pytest.fixture
async def client(web: Web) -> Iterator[AsyncClient]:  # type: ignore[misc]
    app = create_app()
    app.dependency_overrides[get_registry] = lambda: build_registry(fetcher(web.handler))
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def count(session: AsyncSession, model: type[Job] | type[JobSource]) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


async def import_url(client: AsyncClient, url: str, company_id: object = None) -> httpx.Response:
    body = {"url": url, **({"company_id": str(company_id)} if company_id else {})}
    return await client.post("/api/v1/jobs/import-url", json=body)


# --- import from the EURES queue ------------------------------------------------------------


async def test_import_from_queue_links_company_and_marks_job_found(
    client: AsyncClient, session: AsyncSession
) -> None:
    company = await create_company(session, "Example Fintech ApS", "11223344", position=1)
    response = await import_url(client, GH_URL, company.id)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "created"
    job = body["job"]
    assert job["title"] == "Applied AI Engineer"
    assert job["company"] == {
        "id": str(company.id),
        "company_name": "Example Fintech ApS",
        "cvr": "11223344",
    }
    assert job["source_type"] == "greenhouse"
    assert [s["status"] for s in job["sources"]] == ["ACCEPTED"]
    assert "<" not in job["description"]

    detail = (await client.get(f"/api/v1/companies/{company.id}")).json()
    assert detail["eures_status"] == "JOB_FOUND"
    assert detail["eures_last_checked_at"] is not None
    assert detail["jobs_count"] == 1


async def test_reimport_same_url_is_unchanged(client: AsyncClient, session: AsyncSession) -> None:
    first = (await import_url(client, GH_URL)).json()
    second = (await import_url(client, GH_URL)).json()
    assert second["outcome"] == "unchanged"
    assert second["job"]["id"] == first["job"]["id"]
    assert (await count(session, Job), await count(session, JobSource)) == (1, 1)


async def test_changed_content_creates_pending_snapshot_then_accept(
    client: AsyncClient, session: AsyncSession, web: Web
) -> None:
    original = (await import_url(client, GH_URL)).json()["job"]
    changed = json.loads(fixture("greenhouse_job.json"))
    changed["title"] = "Senior Applied AI Engineer"
    web.set(GH_API, lambda: httpx.Response(200, json=changed))

    pending = (await import_url(client, GH_URL)).json()
    assert pending["outcome"] == "update_pending"
    job = pending["job"]
    assert job["title"] == "Applied AI Engineer"  # not silently overwritten
    assert job["source_update_pending"] is True
    snapshot = next(s for s in job["sources"] if s["status"] == "PENDING")
    assert snapshot["normalized"]["title"] == "Senior Applied AI Engineer"

    again = (await import_url(client, GH_URL)).json()
    assert again["outcome"] == "unchanged"  # the pending snapshot is not duplicated
    assert await count(session, JobSource) == 2

    accepted = await client.post(f"/api/v1/jobs/{job['id']}/sources/{snapshot['id']}/accept")
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["title"] == "Senior Applied AI Engineer"
    assert body["source_update_pending"] is False
    assert body["content_hash"] != original["content_hash"]
    assert {s["status"] for s in body["sources"]} == {"ACCEPTED"}

    repeat = await client.post(f"/api/v1/jobs/{job['id']}/sources/{snapshot['id']}/accept")
    assert repeat.status_code == 409


async def test_reject_keeps_original_content(client: AsyncClient, web: Web) -> None:
    await import_url(client, GH_URL)
    changed = json.loads(fixture("greenhouse_job.json"))
    changed["content"] = "&lt;p&gt;Completely different text about something else.&lt;/p&gt;"
    web.set(GH_API, lambda: httpx.Response(200, json=changed))
    job = (await import_url(client, GH_URL)).json()["job"]
    snapshot = next(s for s in job["sources"] if s["status"] == "PENDING")

    body = (await client.post(f"/api/v1/jobs/{job['id']}/sources/{snapshot['id']}/reject")).json()
    assert body["source_update_pending"] is False
    assert body["description"].startswith("About the role")
    assert sorted(s["status"] for s in body["sources"]) == ["ACCEPTED", "REJECTED"]


async def test_same_vacancy_at_another_url_attaches_source(
    client: AsyncClient, session: AsyncSession, web: Web
) -> None:
    web.set(
        "careers.example.com/jobs/1042?ref=linkedin",
        lambda: html_response(fixture("jsonld_basic.html")),
    )
    first = (await import_url(client, PAGE_URL)).json()
    second = (await import_url(client, f"{PAGE_URL}?ref=linkedin")).json()
    assert second["outcome"] == "attached_source"
    assert second["job"]["id"] == first["job"]["id"]
    assert len(second["job"]["sources"]) == 2
    assert await count(session, Job) == 1


async def test_exact_employer_name_links_without_changing_eures_status(
    client: AsyncClient, session: AsyncSession
) -> None:
    company = await create_company(session, "Example Robotics A/S", "55667788")
    await create_company(session, "Example Robotics Holding A/S", "55667799")
    job = (await import_url(client, PAGE_URL)).json()["job"]
    assert job["company"]["id"] == str(company.id)
    await session.refresh(company)
    assert company.eures_status is EuresStatus.NOT_CHECKED


async def test_no_company_link_without_exact_match(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_company(session, "Example Robotics Holding A/S", "55667799")
    job = (await import_url(client, PAGE_URL)).json()["job"]
    assert job["company"] is None
    assert job["employer_name"] == "Example Robotics A/S"


# --- errors ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "status", "code"),
    [
        ("https://europa.eu/eures/portal/jv-se/jv-details/abc", 422, "EURES_NOT_ALLOWED"),
        ("http://169.254.169.254/latest/meta-data", 422, "BLOCKED_URL"),
        ("ftp://example.com/job", 422, "BLOCKED_URL"),
        ("https://careers.example.com/missing", 502, "FETCH_FAILED"),
    ],
)
async def test_import_errors_are_structured(
    client: AsyncClient, session: AsyncSession, url: str, status: int, code: str
) -> None:
    response = await import_url(client, url)
    assert response.status_code == status
    detail = response.json()["detail"]
    assert detail["code"] == code
    assert detail["retryable"] is False
    assert await count(session, Job) == 0


async def test_robots_disallow_suggests_manual_paste(client: AsyncClient, web: Web) -> None:
    web.set(
        "careers.example.com/robots.txt",
        lambda: httpx.Response(200, text="User-agent: *\nDisallow: /jobs/"),
    )
    detail = (await import_url(client, PAGE_URL)).json()["detail"]
    assert detail["code"] == "ROBOTS_DISALLOWED"
    assert "manually" in detail["message"]


async def test_failed_import_leaves_company_status_unchanged(
    client: AsyncClient, session: AsyncSession
) -> None:
    company = await create_company(session, "Example Fintech ApS", "11223344")
    await import_url(client, "https://careers.example.com/missing", company.id)
    await session.refresh(company)
    assert company.eures_status is EuresStatus.NOT_CHECKED


async def test_unknown_company_is_404(client: AsyncClient) -> None:
    response = await import_url(client, GH_URL, "00000000-0000-4000-8000-000000000000")
    assert response.status_code == 404


# --- manual paste ------------------------------------------------------------------------------

MANUAL = {
    "title": "  Data   Engineer ",
    "description": (
        "We need a data engineer to build pipelines with Python, Airflow and dbt "
        "for our trading desk."
    ),
    "employer_name": "Paste Co",
    "location": "Odense",
}


async def test_manual_import(client: AsyncClient, session: AsyncSession) -> None:
    company = await create_company(session, "Paste Co ApS", "99887766")
    first = (
        await client.post(
            "/api/v1/jobs/import-text", json={**MANUAL, "company_id": str(company.id)}
        )
    ).json()
    assert first["outcome"] == "created"
    job = first["job"]
    assert (job["title"], job["source_type"], job["location"]) == (
        "Data Engineer",
        "manual",
        "Odense",
    )
    assert job["sources"][0]["source_url"].startswith("manual:")
    await session.refresh(company)
    assert company.eures_status is EuresStatus.JOB_FOUND

    again = (await client.post("/api/v1/jobs/import-text", json=MANUAL)).json()
    assert again["outcome"] == "unchanged"


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"source_url": "https://europa.eu/eures/portal/jv-se/jv-details/1"}, "source_url"),
        ({"apply_url": "javascript:alert(1)"}, "apply_url"),
        ({"description": "too short"}, "description"),
    ],
)
async def test_manual_import_validation(
    client: AsyncClient, override: dict[str, str], field: str
) -> None:
    response = await client.post("/api/v1/jobs/import-text", json={**MANUAL, **override})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == field


# --- listing, detail, delete, company filters ---------------------------------------------------


async def test_list_detail_delete_and_company_filters(
    client: AsyncClient, session: AsyncSession
) -> None:
    company = await create_company(session, "Example Fintech ApS", "11223344", position=1)
    await create_company(session, "Other A/S", "44332211", position=2)
    job_id = (await import_url(client, GH_URL, company.id)).json()["job"]["id"]
    await client.post("/api/v1/jobs/import-text", json=MANUAL)

    listing = (await client.get("/api/v1/jobs")).json()
    assert listing["total"] == 2
    assert listing["items"][0]["title"] == "Data Engineer"  # newest first
    by_company = (await client.get("/api/v1/jobs", params={"company_id": str(company.id)})).json()
    assert [j["id"] for j in by_company["items"]] == [job_id]
    assert (await client.get("/api/v1/jobs", params={"q": "applied ai"})).json()["total"] == 1

    with_jobs = (await client.get("/api/v1/companies", params={"has_jobs": "true"})).json()
    assert [c["company_name"] for c in with_jobs["items"]] == ["Example Fintech ApS"]
    without = (await client.get("/api/v1/companies", params={"has_jobs": "false"})).json()
    assert [c["company_name"] for c in without["items"]] == ["Other A/S"]

    assert (await client.delete(f"/api/v1/jobs/{job_id}")).status_code == 204
    assert (await client.get(f"/api/v1/jobs/{job_id}")).status_code == 404
    detail = (await client.get(f"/api/v1/companies/{company.id}")).json()
    assert detail["jobs_count"] == 0
    assert (await session.scalar(select(func.count()).select_from(Company))) == 2
