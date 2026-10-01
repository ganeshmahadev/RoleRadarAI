import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.discovery.eures_scan import (
    DETAIL_URL,
    USER_AGENT,
    EuresBlocked,
    EuresClient,
    EuresError,
    dedupe,
    legal_id,
    parse_hits,
    search_payload,
    to_job,
)
from app.models import (
    CandidateProfile,
    DiscoveryRun,
    DiscoveryTrigger,
    EuresStatus,
    Job,
    Resume,
    RunStatus,
    SourceType,
)
from app.services import discovery_service as discovery
from app.workers import match_runner
from tests.factories import create_company
from tests.fake_eures import FIXTURES, handler
from tests.test_match_runs import ScriptedProvider, Sleeps

SEARCH = json.loads((FIXTURES / "search.json").read_text())
DETAIL = json.loads((FIXTURES / "detail.json").read_text())


class FakeTime:
    """Monotonic clock that only moves when the client sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def eures(requests: list[httpx.Request] | None = None, time: FakeTime | None = None) -> EuresClient:
    time = time or FakeTime()
    return EuresClient(
        crawl_delay=10, transport=handler(requests), sleep=time.sleep, monotonic=time.monotonic
    )


# --- parsing (fixtures in the shapes the user captured) ----------------------------------------


def test_search_payload_matches_the_browser_request() -> None:
    captured = json.loads((FIXTURES / "search_request.json").read_text())
    assert search_payload("AI Engineer", page=1, session_id="example-session-id") == captured


def test_parse_and_dedupe_hits() -> None:
    hits = parse_hits(SEARCH)
    assert len(hits) == 3
    unique = dedupe(hits)
    assert [(h.employer_name, h.eures_flag) for h in unique] == [
        ("Example Vision ApS", True),  # the EURES-flagged original wins over the English copy
        ("Other Robotics A/S", True),
    ]
    assert unique[0].created == datetime(2026, 9, 21, 14, 13, 20, tzinfo=UTC)


def test_to_job_from_detail() -> None:
    hit = dedupe(parse_hits(SEARCH))[0]
    job = to_job(hit, DETAIL)
    assert job.source_type is SourceType.EURES
    assert job.source_url == DETAIL_URL.format(id=hit.id)
    assert job.external_job_id == hit.id
    assert job.employer_name == "Example Vision ApS"
    assert (job.city, job.location) == ("Aalborg Øst", "Aalborg Øst, Denmark")
    assert job.apply_url == "https://careers.example.com/jobs/42-senior-cv-engineer"
    assert "<" not in job.description
    assert legal_id(DETAIL) == "12345678"


def test_to_job_from_search_hit_only() -> None:
    english_copy = parse_hits(SEARCH)[1]
    job = to_job(english_copy)
    assert job.apply_url == "https://careers.example.com/jobs/42-senior-cv-engineer"
    assert job.location == "Denmark"


# --- client: throttle, headers, blocking -------------------------------------------------------


async def test_client_is_throttled_and_honest() -> None:
    requests: list[httpx.Request] = []
    time = FakeTime()
    client = eures(requests, time)
    await client.search("AI Engineer")
    await client.detail("abc")
    await client.search("Nobody A/S")
    assert time.sleeps == [10, 10]  # robots.txt Crawl-delay between every request
    assert all(r.headers["user-agent"] == USER_AGENT for r in requests)
    assert requests[0].method == "POST" and requests[1].method == "GET"
    assert client.requests == 3


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(429), EuresBlocked),
        (httpx.Response(403), EuresBlocked),
        (
            httpx.Response(200, text="<html>captcha</html>", headers={"content-type": "text/html"}),
            EuresBlocked,
        ),
        (httpx.Response(503), EuresError),
        (httpx.Response(200, json={"unexpected": True}), EuresError),
    ],
)
async def test_client_errors(response: httpx.Response, error: type[Exception]) -> None:
    client = EuresClient(crawl_delay=0, transport=httpx.MockTransport(lambda _: response))
    with pytest.raises(error):
        await client.search("AI Engineer")


async def test_runner_client_never_goes_below_crawl_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "eures_scraper_enabled", False)
    assert match_runner.eures_client() is None  # off by default
    monkeypatch.setattr(get_settings(), "eures_scraper_enabled", True)
    monkeypatch.setattr(get_settings(), "eures_crawl_delay_seconds", 1.0)
    client = match_runner.eures_client()
    assert client is not None and client._delay == 10.0


# --- discovery runs with the EURES phase -------------------------------------------------------


@pytest.fixture(autouse=True)
def eures_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "eures_scraper_enabled", True)


@pytest.fixture
async def resume(session: AsyncSession) -> Resume:
    resume = Resume(
        name="CV",
        original_filename="cv.pdf",
        file_path=f"resumes/{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        raw_text="CV engineer",
        text_hash="r1",
        is_primary=True,
        profile=CandidateProfile(target_roles=["Computer Vision Engineer"]),
    )
    session.add(resume)
    await session.commit()
    return resume


async def run_eures(
    session: AsyncSession, client: EuresClient, *, terms: list[str], companies: int
) -> DiscoveryRun:
    row = await discovery.get_settings_row(session)
    await discovery.update_settings(
        session,
        row,
        {
            "search_terms": terms,
            "eures_enabled": True,
            "eures_companies_per_run": companies,
            "hours_old": 720,
        },
    )
    run = await discovery.create_run(session, DiscoveryTrigger.MANUAL)  # EURES-only run
    result = await discovery.execute_run(
        session,
        run.id,
        client=None,
        provider=ScriptedProvider(),
        eures=client,
        delays=[],
        pause_seconds=0,
        sleep=Sleeps(),
        clock=lambda: datetime(2026, 10, 2, 6, 0, tzinfo=UTC),
    )
    assert result is not None
    await session.refresh(result)
    return result


@pytest.mark.usefixtures("resume")
async def test_company_scan_imports_confirmed_jobs_and_updates_the_queue(
    session: AsyncSession,
) -> None:
    found = await create_company(
        session, "Example Vision ApS", "12345678", position=2, notes="my note"
    )
    quiet = await create_company(session, "Quiet Company A/S", "87654321", position=1)
    done = await create_company(
        session,
        "Checked Recently A/S",
        "11112222",
        position=3,
        status=EuresStatus.JOB_FOUND,
        last_checked_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
    requests: list[httpx.Request] = []
    run = await run_eures(session, eures(requests), terms=["Data Scientist"], companies=2)

    assert run.status is RunStatus.DONE
    scan = next(s for s in run.sources if s["source"] == "eures companies")
    assert (scan["companies_scanned"], scan["companies_with_jobs"], scan["created"]) == (2, 1, 1)
    # Least recently checked first; the company checked yesterday is left for a later run.
    keywords = [
        json.loads(r.content)["keywords"][0]["keyword"] for r in requests if r.method == "POST"
    ]
    assert keywords == ["Data Scientist", "Quiet Company A/S", "Example Vision ApS"]
    assert sum(r.method == "GET" for r in requests) == 1  # one detail call; duplicate hit skipped

    await session.refresh(found)
    await session.refresh(quiet)
    await session.refresh(done)
    assert (found.eures_status, found.eures_checked_by, found.eures_notes) == (
        EuresStatus.JOB_FOUND,
        "scan",
        "my note",
    )
    assert (quiet.eures_status, quiet.eures_checked_by) == (EuresStatus.CHECKED_NO_JOBS, "scan")
    assert quiet.eures_last_checked_at == datetime(2026, 10, 2, 6, 0, tzinfo=UTC)
    assert done.eures_last_checked_at == datetime(2026, 10, 1, tzinfo=UTC)

    job = (await session.execute(select(Job).where(Job.company_id == found.id))).scalar_one()
    assert job.apply_url == "https://careers.example.com/jobs/42-senior-cv-engineer"
    assert job.city == "Aalborg Øst"


@pytest.mark.usefixtures("resume")
async def test_term_search_links_by_cvr_and_company_scan_reuses_it(session: AsyncSession) -> None:
    company = await create_company(session, "Example Vision ApS", "12345678")
    requests: list[httpx.Request] = []
    run = await run_eures(session, eures(requests), terms=["AI Engineer"], companies=1)
    term = next(s for s in run.sources if s["source"] == "eures")
    assert (term["found"], term["created"], term["linked_siri"]) == (2, 2, 1)
    rows = (await session.execute(select(Job.title, Job.company_id).order_by(Job.title))).all()
    assert [tuple(r) for r in rows] == [
        ("AI Engineer", None),  # other employer, not in SIRI
        ("Senior Computer Vision & AI Engineer", company.id),  # linked by legalID = CVR
    ]
    # The company scan finds the same vacancy again and makes no new detail request.
    scan = next(s for s in run.sources if s["source"] == "eures companies")
    assert (scan["unchanged"], scan["created"], scan["companies_with_jobs"]) == (1, 0, 1)
    assert sum(r.method == "GET" for r in requests) == 2
    await session.refresh(company)
    assert (company.eures_status, company.eures_checked_by) == (EuresStatus.JOB_FOUND, "scan")

    # A daily rerun only fetches details for vacancies it has not seen.
    requests.clear()
    await run_eures(session, eures(requests), terms=["AI Engineer"], companies=0)
    assert [r.method for r in requests] == ["POST"]


@pytest.mark.usefixtures("resume")
async def test_same_name_with_another_cvr_is_not_linked(session: AsyncSession) -> None:
    company = await create_company(session, "Example Vision ApS", "99999999")
    run = await run_eures(session, eures(), terms=["Data Scientist"], companies=1)
    scan = next(s for s in run.sources if s["source"] == "eures companies")
    assert (scan["skipped"], scan["created"]) == (1, 0)
    assert await session.scalar(select(Job.id).where(Job.company_id == company.id)) is None


@pytest.mark.usefixtures("resume")
async def test_blocked_eures_stops_the_scan_but_not_the_run(session: AsyncSession) -> None:
    blocked = await create_company(session, "Blocked Company A/S", "10000001", position=1)
    later = await create_company(session, "Example Vision ApS", "12345678", position=2)
    requests: list[httpx.Request] = []
    run = await run_eures(session, eures(requests), terms=["Data Scientist"], companies=5)
    scan = next(s for s in run.sources if s["source"] == "eures companies")
    assert scan["status"] == "blocked" and "429" in scan["message"]
    assert len(requests) == 2  # term search + the blocked company; nothing after the block
    await session.refresh(blocked)
    await session.refresh(later)
    assert blocked.eures_status is EuresStatus.NOT_CHECKED  # not marked as checked
    assert later.eures_last_checked_at is None
    assert run.status is RunStatus.DONE
