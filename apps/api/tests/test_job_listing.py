import uuid
from datetime import UTC, datetime, timedelta
from itertools import count

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CandidateProfile,
    Company,
    Job,
    JobStatus,
    MatchScore,
    MatchStatus,
    Resume,
    SourceType,
)
from app.services.match_service import profile_hash
from tests.factories import create_company

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
_seq = count()


async def make_resume(session: AsyncSession, *, primary: bool = True) -> Resume:
    resume = Resume(
        name="CV",
        original_filename="cv.pdf",
        file_path=f"resumes/{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        raw_text="text",
        text_hash=f"resume-{next(_seq)}",
        is_primary=primary,
        profile=CandidateProfile(),
    )
    session.add(resume)
    await session.commit()
    return resume


async def make_job(
    session: AsyncSession,
    title: str,
    *,
    company: Company | None = None,
    employer: str | None = None,
    location: str | None = None,
    status: JobStatus = JobStatus.NEW,
    source: SourceType = SourceType.MANUAL,
    age_minutes: int = 0,
    pending: bool = False,
) -> Job:
    n = next(_seq)
    job = Job(
        title=title,
        normalized_title=title.lower(),
        employer_name=employer,
        company_id=company.id if company else None,
        description="d",
        location=location,
        source_type=source,
        content_hash=f"job-{n}",
        dedup_key=f"dedup-{n}",
        status=status,
        source_update_pending=pending,
        created_at=T0 - timedelta(minutes=age_minutes),
    )
    session.add(job)
    await session.commit()
    return job


async def make_match(
    session: AsyncSession,
    job: Job,
    resume: Resume,
    score: float,
    *,
    blocked: bool = False,
    status: MatchStatus = MatchStatus.DONE,
    age_minutes: int = 0,
    category: str | None = None,
) -> MatchScore:
    match = MatchScore(
        job_id=job.id,
        resume_id=resume.id,
        status=status,
        input_hash=f"input-{next(_seq)}",
        resume_text_hash=resume.text_hash,
        profile_hash=profile_hash(resume.profile),
        job_content_hash=job.content_hash,
        model_provider="openjev",
        model_name="m",
        model_revision="r",
        rubric_version="rubric_v1",
        overall_score=score,
        category=category or ("BLOCKED" if blocked else "GOOD"),
        hard_blocker=blocked,
        missing_requirements=["Mandatory language"] if blocked else [],
        created_at=T0 - timedelta(minutes=age_minutes),
    )
    session.add(match)
    await session.commit()
    return match


async def titles(client: AsyncClient, **params: object) -> list[str]:
    response = await client.get("/api/v1/jobs", params=params)  # type: ignore[arg-type]
    assert response.status_code == 200, response.text
    return [item["title"] for item in response.json()["items"]]


# --- ranking -----------------------------------------------------------------------------------


async def test_ranking_blocked_last_mixed_and_excluded(
    client: AsyncClient, session: AsyncSession
) -> None:
    resume = await make_resume(session)
    good = await make_job(session, "Good 80")
    blocked = await make_job(session, "Blocked 90")
    best = await make_job(session, "Best 95")
    await make_job(session, "Unscored")
    await make_match(session, good, resume, 80)
    await make_match(session, blocked, resume, 90, blocked=True)
    await make_match(session, best, resume, 95)

    assert await titles(client, sort="match") == ["Best 95", "Good 80", "Blocked 90", "Unscored"]
    assert await titles(client, sort="match", blocked="mixed") == [
        "Best 95",
        "Blocked 90",
        "Good 80",
        "Unscored",
    ]
    assert await titles(client, sort="match", blocked="exclude") == [
        "Best 95",
        "Good 80",
        "Unscored",
    ]
    assert await titles(client, sort="match", scored="true") == ["Best 95", "Good 80", "Blocked 90"]
    assert await titles(client, sort="match", scored="false") == ["Unscored"]
    assert await titles(client, sort="match", min_score=85) == ["Best 95", "Blocked 90"]


async def test_match_is_latest_done_for_the_primary_resume(
    client: AsyncClient, session: AsyncSession
) -> None:
    primary = await make_resume(session)
    other = await make_resume(session, primary=False)
    job = await make_job(session, "Job")
    await make_match(session, job, primary, 60, age_minutes=30)
    await make_match(session, job, primary, 75, age_minutes=10)  # latest DONE wins
    await make_match(session, job, primary, 0, status=MatchStatus.FAILED, age_minutes=1)
    await make_match(session, job, other, 99)  # not the primary resume
    item = (await client.get("/api/v1/jobs")).json()["items"][0]
    assert item["match"]["overall_score"] == 75
    assert item["match_outdated"] is False
    assert item["scoring"] is False


async def test_scoring_in_progress_flag(client: AsyncClient, session: AsyncSession) -> None:
    resume = await make_resume(session)
    job = await make_job(session, "Job")
    await make_match(session, job, resume, 0, status=MatchStatus.RUNNING)
    item = (await client.get("/api/v1/jobs")).json()["items"][0]
    assert item["match"] is None
    assert item["scoring"] is True


async def test_no_primary_resume_means_no_matches(
    client: AsyncClient, session: AsyncSession
) -> None:
    resume = await make_resume(session, primary=False)
    job = await make_job(session, "Job")
    await make_match(session, job, resume, 90)
    assert (await client.get("/api/v1/jobs")).json()["items"][0]["match"] is None


@pytest.mark.parametrize("change", ["profile", "resume", "job", "rubric"])
async def test_outdated_flag(client: AsyncClient, session: AsyncSession, change: str) -> None:
    resume = await make_resume(session)
    job = await make_job(session, "Job")
    match = await make_match(session, job, resume, 80)
    if change == "profile":
        resume.profile.skills = ["Python"]
    elif change == "resume":
        resume.text_hash = "changed"
    elif change == "job":
        job.content_hash = "changed"
    else:
        match.rubric_version = "rubric_v0"
    await session.commit()
    item = (await client.get("/api/v1/jobs")).json()["items"][0]
    assert item["match"]["overall_score"] == 80  # still shown
    assert item["match_outdated"] is True


# --- filters and sorts -------------------------------------------------------------------------


async def test_filters(client: AsyncClient, session: AsyncSession) -> None:
    siri = await create_company(session, "Novo Nordisk A/S", "24256790")
    other = await create_company(session, "Non SIRI ApS", "11111111", siri_certified=False)
    await make_job(session, "ML Engineer", company=siri, location="Copenhagen, Denmark")
    await make_job(
        session, "Data Scientist", company=other, location="Aarhus", source=SourceType.LEVER
    )
    await make_job(session, "Saved One", employer="Acme", status=JobStatus.SAVED, location="Berlin")
    await make_job(session, "Ignored One", status=JobStatus.IGNORED)
    await make_job(session, "Needs Review", pending=True)

    assert "Ignored One" not in await titles(client)  # hidden by default
    assert await titles(client, status="IGNORED") == ["Ignored One"]
    assert sorted(await titles(client, status=["SAVED", "IGNORED"])) == ["Ignored One", "Saved One"]
    assert await titles(client, q="engineer") == ["ML Engineer"]
    assert await titles(client, q="novo") == ["ML Engineer"]  # matches the linked company
    assert await titles(client, location="denmark") == ["ML Engineer"]
    assert await titles(client, siri_only="true") == ["ML Engineer"]
    assert await titles(client, source_type="lever") == ["Data Scientist"]
    assert await titles(client, company_id=str(siri.id)) == ["ML Engineer"]
    assert await titles(client, update_pending="true") == ["Needs Review"]


async def test_sorts(client: AsyncClient, session: AsyncSession) -> None:
    beta = await create_company(session, "Beta A/S", "22222222")
    await make_job(session, "zeta role", employer="Alpha ApS", age_minutes=1)
    await make_job(session, "Alpha role", company=beta, age_minutes=2)
    await make_job(session, "middle role", employer=None, age_minutes=0)
    assert await titles(client, sort="newest") == ["middle role", "zeta role", "Alpha role"]
    assert await titles(client, sort="title") == ["Alpha role", "middle role", "zeta role"]
    assert await titles(client, sort="company") == ["zeta role", "Alpha role", "middle role"]


@pytest.mark.parametrize(
    "params",
    [{"sort": "random"}, {"blocked": "maybe"}, {"min_score": "101"}, {"status": "APPLIED"}],
)
async def test_invalid_parameters(client: AsyncClient, params: dict[str, str]) -> None:
    assert (await client.get("/api/v1/jobs", params=params)).status_code == 422


# --- status ------------------------------------------------------------------------------------


async def test_save_ignore_and_restore(client: AsyncClient, session: AsyncSession) -> None:
    job = await make_job(session, "Job")
    url = f"/api/v1/jobs/{job.id}"
    assert (await client.patch(url, json={"status": "SAVED"})).json()["status"] == "SAVED"
    assert (await client.patch(url, json={"status": "IGNORED"})).json()["status"] == "IGNORED"
    assert await titles(client) == []
    assert (await client.patch(url, json={"status": "NEW"})).json()["status"] == "NEW"
    assert await titles(client) == ["Job"]
    assert (await client.patch(url, json={"status": "APPLIED"})).status_code == 422
    assert (await client.patch(url, json={"title": "x"})).status_code == 422
    assert (
        await client.patch(f"/api/v1/jobs/{uuid.uuid4()}", json={"status": "SAVED"})
    ).status_code == 404


async def test_category_filter_uses_the_stored_band(
    client: AsyncClient, session: AsyncSession
) -> None:
    resume = await make_resume(session)
    strong = await make_job(session, "Strong")
    edge = await make_job(session, "Edge 84.5")
    await make_match(session, strong, resume, 90, category="STRONG")
    await make_match(session, edge, resume, 84.5, category="GOOD")
    assert await titles(client, category="STRONG") == ["Strong"]
    assert (await client.get("/api/v1/jobs", params={"category": "SUPER"})).status_code == 422


async def test_match_detail_reports_outdated(client: AsyncClient, session: AsyncSession) -> None:
    resume = await make_resume(session)
    job = await make_job(session, "Job")
    match = await make_match(session, job, resume, 80)
    assert (await client.get(f"/api/v1/matches/{match.id}")).json()["outdated"] is False
    resume.profile.skills = ["SQL"]
    await session.commit()
    assert (await client.get(f"/api/v1/matches/{match.id}")).json()["outdated"] is True
