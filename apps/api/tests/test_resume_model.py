from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateProfile, RemotePreference, Resume


def make_resume(key: str, *, primary: bool = False) -> Resume:
    return Resume(
        name="Resume",
        original_filename="resume.pdf",
        file_path=key,
        mime_type="application/pdf",
        size_bytes=1234,
        raw_text="Alex Example. Python engineer.",
        text_hash="h",
        is_primary=primary,
        profile=CandidateProfile(),
    )


async def test_defaults_and_profile(session: AsyncSession) -> None:
    session.add(make_resume("a.pdf"))
    await session.commit()
    resume = await session.scalar(select(Resume))
    assert resume is not None
    assert resume.is_primary is False
    assert resume.profile.skills == []
    assert resume.profile.remote_preference is None


async def test_profile_round_trips_structured_values(session: AsyncSession) -> None:
    resume = make_resume("a.pdf")
    resume.profile.languages = [{"language": "English", "level": "C2"}]
    resume.profile.years_experience = Decimal("5.5")
    resume.profile.remote_preference = RemotePreference.HYBRID
    session.add(resume)
    await session.commit()
    session.expunge_all()
    stored = await session.scalar(select(CandidateProfile))
    assert stored is not None
    assert stored.languages == [{"language": "English", "level": "C2"}]
    assert stored.years_experience == Decimal("5.5")
    assert stored.remote_preference is RemotePreference.HYBRID


async def test_only_one_primary_resume(session: AsyncSession) -> None:
    session.add_all([make_resume("a.pdf", primary=True), make_resume("b.pdf", primary=False)])
    await session.commit()
    session.add(make_resume("c.pdf", primary=True))
    with pytest.raises(IntegrityError, match="uq_resumes_single_primary"):
        await session.commit()


async def test_one_profile_per_resume_and_cascade(session: AsyncSession) -> None:
    resume = make_resume("a.pdf")
    session.add(resume)
    await session.commit()
    await session.delete(resume)
    await session.commit()
    assert (await session.execute(select(CandidateProfile))).first() is None


async def test_database_rejects_unknown_remote_preference(session: AsyncSession) -> None:
    session.add(make_resume("a.pdf"))
    await session.commit()
    with pytest.raises(IntegrityError, match="ck_candidate_profiles_remote_preference"):
        await session.execute(text("UPDATE candidate_profiles SET remote_preference = 'moon'"))
