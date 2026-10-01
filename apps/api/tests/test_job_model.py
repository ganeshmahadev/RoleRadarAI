from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, JobSource, SnapshotStatus, SourceType
from tests.factories import create_company

NOW = datetime(2026, 10, 1, tzinfo=UTC)


def make_job(dedup_key: str = "k1", **overrides: object) -> Job:
    fields: dict[str, object] = {
        "title": "ML Engineer",
        "normalized_title": "ml engineer",
        "description": "Build models.",
        "source_type": SourceType.JSONLD,
        "content_hash": "h1",
        "dedup_key": dedup_key,
    }
    fields.update(overrides)
    return Job(**fields)


def make_source(
    job: Job, url: str = "https://example.com/jobs/1", content_hash: str = "h1"
) -> JobSource:
    return JobSource(
        job=job,
        source_type=SourceType.JSONLD,
        source_url=url,
        content_hash=content_hash,
        normalized={"title": "ML Engineer"},
        fetched_at=NOW,
    )


async def test_job_with_sources(session: AsyncSession) -> None:
    job = make_job()
    session.add_all([job, make_source(job), make_source(job, content_hash="h2")])
    await session.commit()
    stored = await session.scalar(select(Job))
    assert stored is not None
    await session.refresh(stored, ["sources"])
    assert len(stored.sources) == 2
    assert stored.source_update_pending is False
    assert stored.company_id is None
    assert stored.sources[0].status is SnapshotStatus.ACCEPTED


async def test_dedup_key_is_unique(session: AsyncSession) -> None:
    session.add_all([make_job("same"), make_job("same")])
    with pytest.raises(IntegrityError, match="uq_jobs_dedup_key"):
        await session.commit()


async def test_same_url_and_hash_is_unique(session: AsyncSession) -> None:
    job = make_job()
    session.add_all([job, make_source(job), make_source(job)])
    with pytest.raises(IntegrityError, match="uq_job_sources_source_url_content_hash"):
        await session.commit()


async def test_deleting_company_keeps_job(session: AsyncSession) -> None:
    company = await create_company(session, "3Shape A/S", "25553489")
    job = make_job(company_id=company.id)
    session.add(job)
    await session.commit()
    await session.delete(company)
    await session.commit()
    await session.refresh(job)
    assert job.company_id is None


async def test_deleting_job_deletes_sources(session: AsyncSession) -> None:
    job = make_job()
    session.add_all([job, make_source(job)])
    await session.commit()
    await session.delete(job)
    await session.commit()
    assert (await session.execute(select(JobSource))).first() is None
