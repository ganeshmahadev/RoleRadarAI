import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.discovery.jobspy_source import SearchSpec, build_params, is_blocked, row_to_job
from app.main import create_app
from app.models import (
    CandidateProfile,
    DiscoveryRun,
    DiscoveryTrigger,
    Job,
    JobSource,
    MatchScore,
    Resume,
    RunStatus,
    SourceType,
)
from app.services import discovery_service as discovery
from app.services.match_queue import get_match_queue
from tests.factories import create_company
from tests.fake_jobspy import FakeJobSpyClient
from tests.test_match_runs import ScriptedProvider, Sleeps

TERM = "Machine Learning Engineer"


# --- JobSpy mapping (no network) -------------------------------------------------------------


def test_build_params_per_site() -> None:
    spec = SearchSpec("indeed", TERM, "Denmark", 25, 72)
    assert build_params(spec) == {
        "site_name": ["indeed"],
        "search_term": TERM,
        "location": "Denmark",
        "results_wanted": 25,
        "hours_old": 72,
        "description_format": "html",
        "verbose": 0,
        "country_indeed": "denmark",
    }
    assert build_params(SearchSpec("linkedin", TERM, "Denmark", 5, 72))["fetch_description"] is True
    google = build_params(SearchSpec("google", TERM, "Denmark", 5, 24))
    assert google["google_search_term"] == f"{TERM} jobs in Denmark since yesterday"
    assert "proxies" not in google and "user_agent" not in google  # guardrail: no evasion


def test_row_mapping() -> None:
    row = FakeJobSpyClient().scrape(build_params(SearchSpec("indeed", TERM, "Denmark", 5, 72)))[0]
    job = row_to_job(row, "indeed")
    assert job is not None
    assert job.source_type is SourceType.INDEED
    assert job.title == f"Senior {TERM}"
    assert job.employer_name == "3Shape A/S"
    assert job.apply_url == "https://careers.3shape.example.test/jobs/1"
    assert job.published_at == datetime(2026, 10, 1, tzinfo=UTC)
    assert job.description.startswith(f"We are hiring a {TERM}")
    assert "<" not in job.description


@pytest.mark.parametrize(
    "row",
    [
        {"job_url": "https://x.test/1", "title": "T", "description": None},
        {"job_url": "https://x.test/1", "title": None, "description": "<p>" + "x" * 200 + "</p>"},
        {"job_url": "javascript:alert(1)", "title": "T", "description": "<p>" + "x" * 200 + "</p>"},
        {"job_url": "https://x.test/1", "title": "T", "description": "<p>short</p>"},
    ],
)
def test_unusable_rows_are_skipped(row: dict[str, object]) -> None:
    assert row_to_job(row, "indeed") is None


def test_published_date_variants() -> None:
    base = {
        "job_url": "https://x.test/1",
        "title": "T",
        "description": "<p>" + "word " * 40 + "</p>",
    }
    assert row_to_job(
        {**base, "date_posted": date(2026, 9, 30)}, "google"
    ).published_at == datetime(2026, 9, 30, tzinfo=UTC)  # type: ignore[union-attr]
    assert row_to_job({**base, "date_posted": "not a date"}, "google").published_at is None  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("message", "blocked"),
    [
        ("HTTP 429 Too Many Requests", True),
        ("403 Forbidden", True),
        ("captcha required", True),
        ("timeout", False),
    ],
)
def test_block_detection(message: str, blocked: bool) -> None:
    assert is_blocked(RuntimeError(message)) is blocked


# --- orchestrated runs -------------------------------------------------------------------------


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(get_settings(), "discovery_jobspy_enabled", True)
    yield


@pytest.fixture
async def resume(session: AsyncSession) -> Resume:
    resume = Resume(
        name="CV",
        original_filename="cv.pdf",
        file_path=f"resumes/{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        raw_text="ML engineer",
        text_hash="r1",
        is_primary=True,
        profile=CandidateProfile(target_roles=[TERM]),
    )
    session.add(resume)
    await session.commit()
    return resume


async def run_discovery(
    session: AsyncSession, client: FakeJobSpyClient | None, **settings: object
) -> DiscoveryRun:
    row = await discovery.get_settings_row(session)
    await discovery.update_settings(session, row, dict(settings))
    run = await discovery.create_run(session, DiscoveryTrigger.MANUAL)
    sleeps = Sleeps()
    result = await discovery.execute_run(
        session,
        run.id,
        client=client,
        provider=ScriptedProvider(),
        delays=[],
        pause_seconds=5,
        sleep=sleeps,
    )
    assert result is not None
    await session.refresh(result)
    return result


@pytest.mark.usefixtures("enabled", "resume")
async def test_search_imports_dedups_links_siri_and_scores(session: AsyncSession) -> None:
    siri = await create_company(session, "3Shape A/S", "25553489")
    client = FakeJobSpyClient()
    run = await run_discovery(session, client)

    assert run.status is RunStatus.DONE
    assert [c["site_name"][0] for c in client.calls] == ["indeed", "linkedin", "google"]
    by_source = {s["source"]: s for s in run.sources}
    assert by_source["indeed"]["found"] == 3
    assert by_source["indeed"]["created"] == 2  # Senior … + Office Manager
    assert by_source["indeed"]["skipped"] == 1  # no description
    assert by_source["indeed"]["linked_siri"] == 1
    assert by_source["linkedin"]["attached"] == 1  # same vacancy on another board
    assert by_source["google"]["created"] == 1

    jobs = (await session.execute(select(Job).order_by(Job.title))).scalars().all()
    assert [j.title for j in jobs] == [f"Lead {TERM}", "Office Manager", f"Senior {TERM}"]
    senior = next(j for j in jobs if j.title.startswith("Senior"))
    assert senior.company_id == siri.id
    assert "Posted on indeed" in senior.description  # first board's text kept
    sources = (
        (await session.execute(select(JobSource).where(JobSource.job_id == senior.id)))
        .scalars()
        .all()
    )
    assert {s.source_type for s in sources} == {SourceType.INDEED, SourceType.LINKEDIN}

    # Scoring: only titles matching the target role, the office job is never scored.
    scored = (
        (await session.execute(select(Job.title).join(MatchScore, MatchScore.job_id == Job.id)))
        .scalars()
        .all()
    )
    assert sorted(scored) == [f"Lead {TERM}", f"Senior {TERM}"]
    assert {j["title"] for j in run.new_jobs} == {
        f"Senior {TERM}",
        "Office Manager",
        f"Lead {TERM}",
    }
    assert run.phase.value == "FINISHED" and run.match_run_id is not None


@pytest.mark.usefixtures("enabled", "resume")
async def test_blocked_board_does_not_stop_the_run(session: AsyncSession) -> None:
    run = await run_discovery(
        session, FakeJobSpyClient(fail_site="linkedin"), search_terms=[TERM, "Data Scientist"]
    )
    linkedin = [s for s in run.sources if s["source"] == "linkedin"]
    assert [s["status"] for s in linkedin] == ["blocked", "skipped"]  # no retry around a block
    assert "429" in linkedin[0]["message"]
    assert any(s["source"] == "google" and s["status"] == "ok" for s in run.sources)
    assert run.status is RunStatus.DONE


@pytest.mark.usefixtures("enabled", "resume")
async def test_rerun_finds_nothing_new_and_skips_scoring(session: AsyncSession) -> None:
    await run_discovery(session, FakeJobSpyClient())
    again = await run_discovery(session, FakeJobSpyClient())
    assert sum(s["created"] for s in again.sources) == 0
    scoring = next(s for s in again.sources if s["source"] == "scoring")
    assert scoring["status"] == "skipped"
    assert await session.scalar(select(func.count()).select_from(Job)) == 3


@pytest.mark.usefixtures("enabled", "resume")
async def test_eures_reported_unavailable_until_confirmed(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "eures_scraper_enabled", True)
    run = await run_discovery(session, FakeJobSpyClient(), eures_enabled=True)
    eures = next(s for s in run.sources if s["source"] == "eures")
    assert eures["status"] == "unavailable"


@pytest.mark.usefixtures("enabled", "resume")
async def test_scrape_budget_skips_remaining_searches(session: AsyncSession) -> None:
    row = await discovery.get_settings_row(session)
    await discovery.update_settings(session, row, {"scrape_budget_minutes": 1})
    run = await discovery.create_run(session, DiscoveryTrigger.SCHEDULED)
    start_at = datetime(2026, 10, 2, 6, 0, tzinfo=UTC)
    ticks = iter(start_at + timedelta(seconds=40 * i) for i in range(1000))
    result = await discovery.execute_run(
        session,
        run.id,
        client=FakeJobSpyClient(),
        provider=ScriptedProvider(),
        delays=[],
        pause_seconds=0,
        sleep=Sleeps(),
        clock=lambda: next(ticks),
    )
    assert result is not None
    statuses = [(s["source"], s["status"]) for s in result.sources if s["source"] != "scoring"]
    assert ("google", "skipped") in statuses
    assert result.trigger is DiscoveryTrigger.SCHEDULED


async def test_guardrails_disabled_and_no_terms(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(discovery.DiscoveryDisabled, match="DISCOVERY_JOBSPY_ENABLED"):
        await discovery.create_run(session, DiscoveryTrigger.MANUAL)
    monkeypatch.setattr(get_settings(), "discovery_jobspy_enabled", True)
    with pytest.raises(discovery.NoSearchTerms):
        await discovery.create_run(session, DiscoveryTrigger.MANUAL)


@pytest.mark.usefixtures("enabled", "resume")
async def test_one_active_run_and_cancel(session: AsyncSession) -> None:
    run = await discovery.create_run(session, DiscoveryTrigger.MANUAL)
    with pytest.raises(discovery.DiscoveryAlreadyActive):
        await discovery.create_run(session, DiscoveryTrigger.MANUAL)
    await discovery.cancel_run(session, run)
    assert run.status is RunStatus.CANCELLED
    result = await discovery.execute_run(
        session,
        run.id,
        client=FakeJobSpyClient(),
        provider=ScriptedProvider(),
        delays=[],
        pause_seconds=0,
    )
    assert result is not None and result.status is RunStatus.CANCELLED  # never started


# --- API ---------------------------------------------------------------------------------------


class RecordingQueue:
    def __init__(self) -> None:
        self.discovery: list[uuid.UUID] = []

    async def enqueue(self, match_id: uuid.UUID) -> None: ...

    async def enqueue_run(self, run_id: uuid.UUID) -> None: ...

    async def enqueue_discovery(self, run_id: uuid.UUID) -> None:
        self.discovery.append(run_id)


@pytest.fixture
def queue() -> RecordingQueue:
    return RecordingQueue()


@pytest.fixture
async def client(queue: RecordingQueue) -> AsyncIterator[AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_match_queue] = lambda: queue
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.usefixtures("resume")
async def test_settings_api(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/discovery/settings")).json()
    assert body["sites"] == ["indeed", "linkedin", "google"]
    assert body["effective_terms"] == [TERM]  # from the profile
    assert body["jobspy_enabled"] is False and body["eures_available"] is False
    updated = (
        await client.put(
            "/api/v1/discovery/settings",
            json={
                "search_terms": [" AI Engineer ", "ai engineer"],
                "results_per_site": 10,
                "sites": ["indeed"],
            },
        )
    ).json()
    assert updated["search_terms"] == ["AI Engineer"]
    assert updated["effective_terms"] == ["AI Engineer"]
    assert (updated["results_per_site"], updated["sites"]) == (10, ["indeed"])
    for bad in ({"sites": ["glassdoor"]}, {"results_per_site": 0}, {"proxies": ["x"]}):
        assert (await client.put("/api/v1/discovery/settings", json=bad)).status_code == 422


@pytest.mark.usefixtures("resume", "enabled")
async def test_start_get_cancel_api(client: AsyncClient, queue: RecordingQueue) -> None:
    started = await client.post("/api/v1/discovery-runs", json={})
    assert started.status_code == 202
    body = started.json()
    assert (body["status"], body["trigger"], body["phase"]) == ("QUEUED", "manual", "QUEUED")
    assert body["settings"]["terms"] == [TERM]
    assert queue.discovery == [uuid.UUID(body["id"])]
    assert (await client.post("/api/v1/discovery-runs", json={})).status_code == 409
    assert [r["id"] for r in (await client.get("/api/v1/discovery-runs")).json()] == [body["id"]]
    cancelled = (await client.post(f"/api/v1/discovery-runs/{body['id']}/cancel")).json()
    assert cancelled["status"] == "CANCELLED"
    events = await client.get(f"/api/v1/discovery-runs/{body['id']}/events")
    assert events.text.endswith("event: end\ndata: {}\n\n")
    assert (await client.get(f"/api/v1/discovery-runs/{uuid.uuid4()}")).status_code == 404


async def test_start_is_refused_when_disabled(client: AsyncClient) -> None:
    response = await client.post("/api/v1/discovery-runs", json={})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DISCOVERY_DISABLED"


def test_discovery_task_registered() -> None:
    from app.workers.celery_app import celery_app

    celery_app.loader.import_default_modules()
    assert celery_app.tasks["roleradar.discovery_run"].acks_late is False
