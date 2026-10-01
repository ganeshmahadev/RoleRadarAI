import dataclasses
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import create_app
from app.matching import rubric as rubric_module
from app.matching.rubric import RUBRIC_V1, RUBRICS
from app.models import CandidateProfile, Job, MatchScore, MatchStatus, Resume, SourceType
from app.providers.decision import DecisionUnavailable
from app.providers.factory import get_decision_provider
from app.providers.openjev import OpenJevProvider
from app.services import match_service
from app.services.match_queue import InlineMatchQueue, QueueUnavailable, get_match_queue
from tests.fake_openjev import VERSION, FakeOpenJev

DESCRIPTION = "We need a Machine Learning Engineer with Python and PyTorch. Danish is mandatory."


class RecordingQueue:
    def __init__(self, fail: bool = False) -> None:
        self.ids: list[uuid.UUID] = []
        self.fail = fail

    async def enqueue(self, match_id: uuid.UUID) -> None:
        if self.fail:
            raise QueueUnavailable("redis down")
        self.ids.append(match_id)


def make_provider(fake: FakeOpenJev) -> OpenJevProvider:
    return OpenJevProvider(
        "http://openjev.test", timeout_seconds=5, transport=fake.transport(), backoff_seconds=0
    )


@pytest.fixture
def fake() -> FakeOpenJev:
    return FakeOpenJev()


@pytest.fixture
def queue() -> RecordingQueue:
    return RecordingQueue()


@pytest.fixture
async def client(fake: FakeOpenJev, queue: RecordingQueue) -> AsyncIterator[AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_decision_provider] = lambda: make_provider(fake)
    app.dependency_overrides[get_match_queue] = lambda: queue
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def job(session: AsyncSession) -> Job:
    job = Job(
        title="Machine Learning Engineer",
        normalized_title="machine learning engineer",
        employer_name="Example Robotics A/S",
        description=DESCRIPTION,
        location="Copenhagen",
        source_type=SourceType.MANUAL,
        content_hash="job-hash-1",
        dedup_key="dedup-1",
    )
    session.add(job)
    await session.commit()
    return job


@pytest.fixture
async def resume(session: AsyncSession) -> Resume:
    resume = Resume(
        name="CV",
        original_filename="cv.pdf",
        file_path=f"resumes/{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        raw_text="Alex Example. 5 years Python and PyTorch.",
        text_hash="resume-hash-1",
        is_primary=True,
        profile=CandidateProfile(
            skills=["Python"], languages=[{"language": "English", "level": "C2"}]
        ),
    )
    session.add(resume)
    await session.commit()
    return resume


async def score(client: AsyncClient, job: Job) -> httpx.Response:
    return await client.post(f"/api/v1/jobs/{job.id}/score")


async def run(
    session: AsyncSession, fake: FakeOpenJev, match_id: str | uuid.UUID
) -> MatchScore | None:
    return await match_service.run_match(session, make_provider(fake), uuid.UUID(str(match_id)))


# --- request → run → cache -----------------------------------------------------------------


@pytest.mark.usefixtures("resume")
async def test_score_queues_runs_and_caches(
    client: AsyncClient, session: AsyncSession, fake: FakeOpenJev, queue: RecordingQueue, job: Job
) -> None:
    fake.scores = {"dim_skills": 3.7, "dim_experience": 3.0}
    first = await score(client, job)
    assert first.status_code == 202
    body = first.json()
    assert body["cached"] is False
    match_id = body["match"]["id"]
    assert body["match"]["status"] == "QUEUED"
    assert queue.ids == [uuid.UUID(match_id)]
    assert body["match"]["rubric_version"] == "rubric_v1"
    assert body["match"]["model_revision"].startswith("openjev-MLX-4bit;T=0.85")

    await run(session, fake, match_id)
    done = (await client.get(f"/api/v1/matches/{match_id}")).json()
    assert done["status"] == "DONE"
    assert done["dimensions"]["skills"] == 92.5
    assert done["dimensions"]["experience"] == 75.0
    assert done["dimensions"]["must_have"] is None  # nothing stated (default yes = 0.1)
    assert done["category"] in {"STRONG", "GOOD", "STRETCH", "LOW"}
    assert done["hard_blocker"] is False
    assert done["explanation"]["dimensions"]["skills"]["expected_level"] == 3.7
    assert done["explanation"]["input_tokens"] == 1234
    assert len(fake.requests) == 1  # no requirement stated → no second phase

    again = await score(client, job)
    assert again.status_code == 200
    assert again.json()["cached"] is True
    assert again.json()["match"]["id"] == match_id
    assert queue.ids == [uuid.UUID(match_id)]


@pytest.mark.usefixtures("resume")
async def test_state_follows_prd_layout(
    client: AsyncClient, session: AsyncSession, fake: FakeOpenJev, job: Job
) -> None:
    match_id = (await score(client, job)).json()["match"]["id"]
    await run(session, fake, match_id)
    state = fake.requests[0]["state"]
    assert state.startswith("CANDIDATE\nTarget roles: not stated\nSkills: Python")
    assert "Languages: English (C2)" in state
    assert "Full resume evidence:\nAlex Example. 5 years Python and PyTorch." in state
    assert "VACANCY\nCompany: Example Robotics A/S\nRole: Machine Learning Engineer" in state
    assert state.endswith(DESCRIPTION)


@pytest.mark.usefixtures("resume")
async def test_stated_requirement_not_met_blocks(
    client: AsyncClient, session: AsyncSession, fake: FakeOpenJev, job: Job
) -> None:
    fake.default_score = 4.0
    fake.yes = {"req_language_stated": 0.97, "req_language_met": 0.012}
    match_id = (await score(client, job)).json()["match"]["id"]
    await run(session, fake, match_id)
    assert set(fake.requests[1]["questions"]) == {"req_language_met"}  # only stated types
    done = (await client.get(f"/api/v1/matches/{match_id}")).json()
    assert done["category"] == "BLOCKED"
    assert done["hard_blocker"] is True
    assert done["missing_requirements"] == ["Mandatory language"]
    language = next(r for r in done["requirements"] if r["key"] == "language")
    assert language == {
        "key": "language",
        "label": "Mandatory language",
        "status": "NOT_MET",
        "classification": "blocker",
        "stated_probability": 0.97,
        "met_probability": 0.012,
    }
    assert done["dimensions"]["must_have"] == pytest.approx(1.2)
    assert done["overall_score"] == pytest.approx(round(0.30 * 1.2 + 0.70 * 100, 1))


# --- cache invalidation (P5 acceptance) ------------------------------------------------------


async def _match_id(client: AsyncClient, job: Job) -> str:
    response = await score(client, job)
    assert response.status_code in (200, 202)
    value: str = response.json()["match"]["id"]
    return value


@pytest.mark.parametrize("change", ["resume", "profile", "job", "model"])
async def test_changing_an_input_invalidates_the_cache(
    client: AsyncClient,
    session: AsyncSession,
    fake: FakeOpenJev,
    job: Job,
    resume: Resume,
    change: str,
) -> None:
    first = await _match_id(client, job)
    await run(session, fake, first)
    assert await _match_id(client, job) == first  # unchanged → cached

    if change == "resume":
        resume.text_hash = "resume-hash-2"
    elif change == "profile":
        resume.profile.skills = ["Python", "SQL"]
    elif change == "job":
        job.content_hash = "job-hash-2"
    else:
        fake.version = {**VERSION, "T": 0.9}
    await session.commit()

    response = await score(client, job)
    assert response.status_code == 202
    assert response.json()["match"]["id"] != first


@pytest.mark.usefixtures("resume")
async def test_changing_rubric_version_invalidates_the_cache(
    session: AsyncSession, fake: FakeOpenJev, job: Job, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = make_provider(fake)
    first, created = await match_service.request_score(session, provider, job_id=job.id)
    assert created
    same, created = await match_service.request_score(session, provider, job_id=job.id)
    assert (same.id, created) == (first.id, False)

    variant = dataclasses.replace(RUBRIC_V1, version="rubric_test")
    monkeypatch.setitem(RUBRICS, "rubric_test", variant)
    other, created = await match_service.request_score(
        session, provider, job_id=job.id, rubric=variant
    )
    assert created and other.id != first.id
    assert other.rubric_version == "rubric_test"
    assert rubric_module.CURRENT_RUBRIC.version == "rubric_v1"


@pytest.mark.usefixtures("resume")
async def test_in_flight_request_is_not_duplicated(
    client: AsyncClient, queue: RecordingQueue, job: Job
) -> None:
    first = await score(client, job)
    second = await score(client, job)
    assert second.status_code == 200
    assert second.json()["cached"] is False
    assert second.json()["match"]["id"] == first.json()["match"]["id"]
    assert len(queue.ids) == 1


# --- failures ----------------------------------------------------------------------------------


@pytest.mark.usefixtures("resume")
async def test_openjev_down_at_request_creates_nothing(
    client: AsyncClient, session: AsyncSession, fake: FakeOpenJev, job: Job
) -> None:
    fake.fail_with = 503
    response = await score(client, job)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "DECISION_PROVIDER_UNAVAILABLE"
    assert await session.scalar(select(func.count()).select_from(MatchScore)) == 0


async def test_no_primary_resume_is_409(client: AsyncClient, job: Job) -> None:
    response = await score(client, job)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "NO_PRIMARY_RESUME"


async def test_unknown_job_is_404(client: AsyncClient) -> None:
    response = await client.post(f"/api/v1/jobs/{uuid.uuid4()}/score")
    assert response.status_code == 404
    assert (await client.get(f"/api/v1/matches/{uuid.uuid4()}")).status_code == 404


@pytest.mark.usefixtures("resume")
async def test_openjev_down_during_run_requeues_then_fails(
    client: AsyncClient, session: AsyncSession, fake: FakeOpenJev, job: Job
) -> None:
    match_id = await _match_id(client, job)
    broken = FakeOpenJev()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/systemone":
            return httpx.Response(503)
        return broken.handler(request)

    provider = OpenJevProvider(
        "http://x", timeout_seconds=5, transport=httpx.MockTransport(handler), backoff_seconds=0
    )
    with pytest.raises(DecisionUnavailable):
        await match_service.run_match(session, provider, uuid.UUID(match_id))
    match = await session.get_one(MatchScore, uuid.UUID(match_id))
    await session.refresh(match)
    assert match.status is MatchStatus.QUEUED
    assert match.error_code == "DECISION_PROVIDER_UNAVAILABLE"
    assert match.attempts == 1

    await match_service.mark_failed(session, match.id, "DECISION_PROVIDER_UNAVAILABLE", "gave up")
    failed = await session.get_one(MatchScore, match.id, populate_existing=True)
    assert failed.status is MatchStatus.FAILED

    retry = await score(client, job)  # a failed match never blocks a new attempt
    assert retry.status_code == 202
    assert retry.json()["match"]["id"] != match_id


@pytest.mark.usefixtures("resume")
async def test_input_changed_after_request_fails_cleanly(
    client: AsyncClient, session: AsyncSession, fake: FakeOpenJev, job: Job
) -> None:
    match_id = await _match_id(client, job)
    job.content_hash = "accepted-new-content"
    await session.commit()
    match = await run(session, fake, match_id)
    assert match is not None
    assert (match.status, match.error_code) == (MatchStatus.FAILED, "INPUT_CHANGED")
    assert fake.requests == []  # the model was never asked


@pytest.mark.usefixtures("resume")
async def test_queue_failure_marks_match_failed(
    fake: FakeOpenJev, session: AsyncSession, job: Job
) -> None:
    app = create_app()
    app.dependency_overrides[get_decision_provider] = lambda: make_provider(fake)
    app.dependency_overrides[get_match_queue] = lambda: RecordingQueue(fail=True)
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        response = await c.post(f"/api/v1/jobs/{job.id}/score")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "QUEUE_UNAVAILABLE"
    match = await session.scalar(select(MatchScore))
    assert match is not None and match.status is MatchStatus.FAILED


@pytest.mark.usefixtures("resume")
async def test_deleting_the_job_removes_its_matches(
    client: AsyncClient, session: AsyncSession, job: Job
) -> None:
    await _match_id(client, job)
    assert (await client.delete(f"/api/v1/jobs/{job.id}")).status_code == 204
    assert await session.scalar(select(func.count()).select_from(MatchScore)) == 0


@pytest.mark.usefixtures("resume")
async def test_list_matches_for_job(
    client: AsyncClient, session: AsyncSession, fake: FakeOpenJev, job: Job
) -> None:
    match_id = await _match_id(client, job)
    listing = (await client.get("/api/v1/matches", params={"job_id": str(job.id)})).json()
    assert [m["id"] for m in listing] == [match_id]
    assert (await client.get("/api/v1/matches", params={"job_id": str(uuid.uuid4())})).json() == []


# --- queue + worker wiring ---------------------------------------------------------------------


@pytest.mark.usefixtures("resume")
async def test_inline_queue_runs_the_match(
    session: AsyncSession, fake: FakeOpenJev, job: Job, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.workers import match_runner

    monkeypatch.setattr(match_runner, "get_decision_provider", lambda: make_provider(fake))
    match, _ = await match_service.request_score(session, make_provider(fake), job_id=job.id)
    inline = InlineMatchQueue()
    await inline.enqueue(match.id)
    await inline.drain()
    await session.refresh(match)
    assert match.status is MatchStatus.DONE


def test_celery_task_is_registered() -> None:
    from app.workers.celery_app import celery_app

    celery_app.loader.import_default_modules()
    assert "roleradar.score_match" in celery_app.tasks


def test_long_inputs_are_truncated() -> None:
    variant = dataclasses.replace(RUBRIC_V1, max_resume_chars=10, max_description_chars=10)
    job = Job(title="T", description="d" * 50, source_type=SourceType.MANUAL)
    resume = Resume(
        raw_text="r" * 50,
        profile=CandidateProfile(
            target_roles=[],
            skills=[],
            industries=[],
            education=[],
            certifications=[],
            languages=[],
            preferred_locations=[],
            work_authorization=[],
        ),
    )
    state, truncated = match_service.build_state(variant, job, resume)
    assert truncated == {"resume": True, "description": True}
    assert "r" * 10 + "\n[… truncated]" in state
    assert "Years of experience: not stated" in state
