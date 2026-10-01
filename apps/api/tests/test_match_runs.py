import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_sessionmaker
from app.main import create_app
from app.models import (
    CandidateProfile,
    Job,
    JobStatus,
    MatchRun,
    MatchScore,
    MatchStatus,
    Resume,
    RunItemStatus,
    RunScope,
    RunStatus,
    SourceType,
)
from app.providers.decision import (
    DecisionInvalidResponse,
    DecisionResult,
    DecisionUnavailable,
    ModelInfo,
    Question,
)
from app.providers.openjev import revision_from_version
from app.services import match_run_service as runs
from app.services import match_service
from app.services.match_queue import get_match_queue
from tests.fake_openjev import FakeOpenJev


class ScriptedProvider:
    """In-process DecisionProvider: answers like the fake server, can fail or block on cue."""

    def __init__(
        self, failures: list[Exception] | None = None, gate: asyncio.Event | None = None
    ) -> None:
        self.fake = FakeOpenJev()
        self.failures = failures or []
        self.gate = gate
        self.calls = 0

    async def model_info(self) -> ModelInfo:
        return revision_from_version(self.fake.version)

    async def decide(self, state: str, questions: dict[str, Question]) -> DecisionResult:
        self.calls += 1
        if self.gate is not None:
            await self.gate.wait()
        if self.failures:
            raise self.failures.pop(0)
        body = {"state": state, "questions": {k: q.model_dump() for k, q in questions.items()}}
        answer: dict[str, Any] = self.fake.answer(body)
        return DecisionResult.model_validate(
            {"model": answer["model"], "answers": answer["answers"], "input_tokens": 10}
        )


class Sleeps:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


@pytest.fixture
async def resume(session: AsyncSession) -> Resume:
    resume = Resume(
        name="CV",
        original_filename="cv.pdf",
        file_path=f"resumes/{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        raw_text="Python engineer",
        text_hash="r1",
        is_primary=True,
        profile=CandidateProfile(target_roles=["Machine Learning Engineer", "Data Scientist"]),
    )
    session.add(resume)
    await session.commit()
    return resume


async def add_job(session: AsyncSession, title: str, status: JobStatus = JobStatus.NEW) -> Job:
    key = uuid.uuid4().hex
    job = Job(
        title=title,
        normalized_title=title.lower(),
        description="desc",
        source_type=SourceType.MANUAL,
        content_hash=key,
        dedup_key=key,
        status=status,
    )
    session.add(job)
    await session.commit()
    return job


def statuses(run: MatchRun) -> dict[str, str]:
    return {item.job_title: item.status.value for item in run.items}


# --- planning --------------------------------------------------------------------------------


@pytest.mark.usefixtures("resume")
async def test_plan_applies_relevance_filter_and_scope(session: AsyncSession) -> None:
    await add_job(session, "Senior Machine Learning Engineer")
    await add_job(session, "Office Manager")
    await add_job(session, "Data Scientist", status=JobStatus.IGNORED)  # never in a run
    plan = await runs.plan_run(session, scope=RunScope.UNSCORED_OR_OUTDATED)
    assert plan.relevance_filter is True
    assert [j.title for j in plan.to_score] == ["Senior Machine Learning Engineer"]
    assert plan.to_score[0].matched_role == "Machine Learning Engineer"
    assert [j.title for j in plan.not_relevant] == ["Office Manager"]

    unfiltered = await runs.plan_run(session, scope=RunScope.UNSCORED, apply_relevance_filter=False)
    assert unfiltered.relevance_filter is False
    assert sorted(j.title for j in unfiltered.to_score) == [
        "Office Manager",
        "Senior Machine Learning Engineer",
    ]


async def test_filter_is_off_without_target_roles(session: AsyncSession, resume: Resume) -> None:
    resume.profile.target_roles = []
    await session.commit()
    await add_job(session, "Office Manager")
    plan = await runs.plan_run(session, scope=RunScope.UNSCORED)
    assert plan.relevance_filter is False
    assert [j.title for j in plan.to_score] == ["Office Manager"]


@pytest.mark.usefixtures("resume")
async def test_jobs_scope_and_scored_jobs(session: AsyncSession) -> None:
    a = await add_job(session, "Data Scientist A")
    b = await add_job(session, "Data Scientist B")
    provider = ScriptedProvider()
    match, _ = await match_service.request_score(session, provider, job_id=a.id)
    await match_service.run_match(session, provider, match.id)

    unscored = await runs.plan_run(session, scope=RunScope.UNSCORED)
    assert [j.title for j in unscored.to_score] == ["Data Scientist B"]
    chosen = await runs.plan_run(session, scope=RunScope.JOBS, job_ids=[a.id, b.id])
    assert sorted(j.title for j in chosen.to_score) == ["Data Scientist A", "Data Scientist B"]


async def test_plan_requires_a_primary_resume(session: AsyncSession) -> None:
    with pytest.raises(match_service.NoPrimaryResume):
        await runs.plan_run(session, scope=RunScope.UNSCORED)


# --- execution -------------------------------------------------------------------------------


async def start(session: AsyncSession, scope: RunScope = RunScope.UNSCORED_OR_OUTDATED) -> MatchRun:
    return await runs.create_run(session, await runs.plan_run(session, scope=scope))


@pytest.mark.usefixtures("resume")
async def test_run_scores_relevant_jobs_and_reuses_cache(session: AsyncSession) -> None:
    first = await add_job(session, "Machine Learning Engineer")
    await add_job(session, "Data Scientist")
    await add_job(session, "Office Manager")
    provider = ScriptedProvider()
    run = await runs.create_run(
        session, await runs.plan_run(session, scope=RunScope.JOBS, job_ids=[first.id])
    )
    await runs.execute_run(session, provider, run.id, delays=[])

    run = await start(session, RunScope.UNSCORED_OR_OUTDATED)  # first job is scored → not planned
    assert {i.job_title for i in run.items} == {"Data Scientist", "Office Manager"}
    await runs.execute_run(session, provider, run.id, delays=[])
    await session.refresh(run)
    assert run.status is RunStatus.DONE
    assert statuses(run) == {"Data Scientist": "DONE", "Office Manager": "SKIPPED"}
    assert run.current_job_id is None and run.completed_at is not None
    progress = await runs.progress(session, run)
    assert (progress.finished, progress.total) == (2, 2)
    assert progress.counts["DONE"] == 1 and progress.counts["SKIPPED"] == 1


@pytest.mark.usefixtures("resume")
async def test_identical_input_is_cached_inside_a_run(session: AsyncSession) -> None:
    job = await add_job(session, "Data Scientist")
    provider = ScriptedProvider()
    run = await runs.create_run(
        session, await runs.plan_run(session, scope=RunScope.JOBS, job_ids=[job.id])
    )
    await runs.execute_run(session, provider, run.id, delays=[])
    calls = provider.calls
    again = await runs.create_run(
        session, await runs.plan_run(session, scope=RunScope.JOBS, job_ids=[job.id])
    )
    await runs.execute_run(session, provider, again.id, delays=[])
    await session.refresh(again)
    assert statuses(again) == {"Data Scientist": "CACHED"}
    assert provider.calls == calls  # OpenJev not asked again


@pytest.mark.usefixtures("resume")
async def test_outage_is_retried_with_backoff(session: AsyncSession) -> None:
    await add_job(session, "Data Scientist")
    provider = ScriptedProvider(failures=[DecisionUnavailable("down"), DecisionUnavailable("down")])
    sleeps = Sleeps()
    run = await start(session)
    await runs.execute_run(session, provider, run.id, delays=[1.0, 2.0, 4.0], sleep=sleeps)
    await session.refresh(run)
    assert statuses(run) == {"Data Scientist": "DONE"}
    assert sleeps.calls == [1.0, 2.0]
    match = await session.scalar(select(MatchScore))
    assert match is not None and match.attempts == 3


@pytest.mark.usefixtures("resume")
async def test_persistent_outage_stops_the_run(session: AsyncSession) -> None:
    for title in ("Data Scientist A", "Data Scientist B", "Data Scientist C"):
        await add_job(session, title)
    provider = ScriptedProvider(failures=[DecisionUnavailable("down")] * 10)
    sleeps = Sleeps()
    run = await start(session)
    await runs.execute_run(session, provider, run.id, delays=[1.0, 2.0], sleep=sleeps)
    await session.refresh(run)
    assert run.status is RunStatus.FAILED
    assert run.error_code == "DECISION_PROVIDER_UNAVAILABLE"
    assert sorted(statuses(run).values()) == ["FAILED", "SKIPPED", "SKIPPED"]
    assert sleeps.calls == [1.0, 2.0]  # bounded: not retried for every remaining job
    skipped = [i for i in run.items if i.status is RunItemStatus.SKIPPED]
    assert all(i.reason == "Run stopped: OpenJev unavailable" for i in skipped)
    failed = await session.scalar(select(MatchScore))
    assert failed is not None and failed.status is MatchStatus.FAILED


@pytest.mark.usefixtures("resume")
async def test_non_retryable_failure_only_fails_that_job(session: AsyncSession) -> None:
    await add_job(session, "Data Scientist A")
    await add_job(session, "Data Scientist B")
    provider = ScriptedProvider(failures=[DecisionInvalidResponse("garbled")])
    sleeps = Sleeps()
    run = await start(session)
    await runs.execute_run(session, provider, run.id, delays=[1.0], sleep=sleeps)
    await session.refresh(run)
    assert run.status is RunStatus.DONE
    assert sorted(statuses(run).values()) == ["DONE", "FAILED"]
    failed = next(i for i in run.items if i.status is RunItemStatus.FAILED)
    assert failed.error_code == "DECISION_INVALID_RESPONSE"
    assert sleeps.calls == []  # invalid responses are not retried


@pytest.mark.usefixtures("resume")
async def test_cancel_while_running_stops_after_the_current_job(session: AsyncSession) -> None:
    for title in ("Data Scientist A", "Data Scientist B", "Data Scientist C"):
        await add_job(session, title)
    run = await start(session)
    gate = asyncio.Event()
    provider = ScriptedProvider(gate=gate)

    async def walker() -> None:
        async with get_sessionmaker()() as own:
            await runs.execute_run(own, provider, run.id, delays=[])

    task = asyncio.create_task(walker())
    for _ in range(100):
        await asyncio.sleep(0.02)
        if provider.calls:
            break
    async with get_sessionmaker()() as other:
        await runs.cancel_run(other, await runs.get_run(other, run.id))
    gate.set()
    await task
    await session.refresh(run)
    await session.refresh(run, ["items"])
    assert run.status is RunStatus.CANCELLED
    assert sorted(statuses(run).values()) == ["DONE", "SKIPPED", "SKIPPED"]


@pytest.mark.usefixtures("resume")
async def test_one_active_run_and_nothing_to_score(session: AsyncSession) -> None:
    await add_job(session, "Data Scientist")
    await start(session)
    with pytest.raises(runs.RunAlreadyActive):
        await start(session)
    queued = await session.scalar(select(MatchRun))
    assert queued is not None
    await runs.cancel_run(session, queued)
    assert queued.status is RunStatus.CANCELLED
    assert all(i.status is RunItemStatus.SKIPPED for i in queued.items)
    await add_job(session, "Office Manager")
    with pytest.raises(runs.NothingToScore):
        await runs.create_run(
            session,
            await runs.plan_run(
                session,
                scope=RunScope.JOBS,
                job_ids=[
                    (await session.scalars(select(Job).where(Job.title == "Office Manager")))
                    .one()
                    .id
                ],
            ),
        )


# --- API and SSE -----------------------------------------------------------------------------


class RecordingQueue:
    def __init__(self) -> None:
        self.runs: list[uuid.UUID] = []

    async def enqueue(self, match_id: uuid.UUID) -> None:
        raise AssertionError("not used")

    async def enqueue_run(self, run_id: uuid.UUID) -> None:
        self.runs.append(run_id)


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
async def test_api_preview_start_get_list_cancel(
    client: AsyncClient, session: AsyncSession, queue: RecordingQueue
) -> None:
    await add_job(session, "Data Scientist")
    await add_job(session, "Office Manager")

    preview = (await client.post("/api/v1/match-runs/preview", json={})).json()
    assert [j["title"] for j in preview["to_score"]] == ["Data Scientist"]
    assert [j["title"] for j in preview["not_relevant"]] == ["Office Manager"]
    assert preview["target_roles"] == ["Machine Learning Engineer", "Data Scientist"]

    started = await client.post("/api/v1/match-runs", json={})
    assert started.status_code == 202
    body = started.json()
    assert body["status"] == "QUEUED"
    assert (body["total"], body["finished"]) == (2, 1)  # the irrelevant job is skipped up front
    assert queue.runs == [uuid.UUID(body["id"])]

    assert (await client.post("/api/v1/match-runs", json={})).status_code == 409
    assert (await client.get(f"/api/v1/match-runs/{body['id']}")).json()["id"] == body["id"]
    assert [r["id"] for r in (await client.get("/api/v1/match-runs")).json()] == [body["id"]]

    cancelled = (await client.post(f"/api/v1/match-runs/{body['id']}/cancel")).json()
    assert cancelled["status"] == "CANCELLED"
    assert (await client.get(f"/api/v1/match-runs/{uuid.uuid4()}")).status_code == 404
    assert (
        await client.post("/api/v1/match-runs", json={"scope": "everything"})
    ).status_code == 422


@pytest.mark.usefixtures("resume")
async def test_events_stream_progress_then_end(client: AsyncClient, session: AsyncSession) -> None:
    await add_job(session, "Data Scientist")
    run = await start(session)
    await runs.execute_run(session, ScriptedProvider(), run.id, delays=[])
    response = await client.get(f"/api/v1/match-runs/{run.id}/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [block for block in response.text.split("\n\n") if block]
    assert events[0].startswith("event: progress\ndata: ")
    assert '"status":"DONE"' in events[0]
    assert events[-1] == "event: end\ndata: {}"
    assert (await client.get(f"/api/v1/match-runs/{uuid.uuid4()}/events")).status_code == 404


def test_run_task_is_registered_without_acks_late() -> None:
    from app.workers.celery_app import celery_app

    celery_app.loader.import_default_modules()
    task = celery_app.tasks["roleradar.match_run"]
    assert task.acks_late is False
    assert celery_app.conf.broker_transport_options["visibility_timeout"] >= 4 * 3600
