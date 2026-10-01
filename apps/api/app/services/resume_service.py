"""Resume lifecycle: validate → extract → store → persist (PRD §22). Never logs resume text."""

import logging
import uuid
from pathlib import PurePosixPath

from anyio import to_thread
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateProfile, Resume
from app.providers.storage import StorageProvider
from app.schemas.profile import CandidateProfileUpdate
from app.services.resume_files import sanitize_filename, validate_upload
from app.services.resume_parser import ResumeParser, text_hash

logger = logging.getLogger(__name__)

PROFILE_FIELDS = (
    "target_roles",
    "skills",
    "years_experience",
    "industries",
    "education",
    "certifications",
    "languages",
    "preferred_locations",
    "remote_preference",
    "work_authorization",
)


async def _current_primary(session: AsyncSession) -> Resume | None:
    return await session.scalar(select(Resume).where(Resume.is_primary.is_(True)))


async def create_resume(
    session: AsyncSession,
    storage: StorageProvider,
    parser: ResumeParser,
    *,
    filename: str | None,
    data: bytes,
    name: str | None = None,
) -> Resume:
    upload = validate_upload(filename, data)
    text = await to_thread.run_sync(parser.extract, upload.data, upload.mime_type)
    key = await to_thread.run_sync(
        lambda: storage.save(upload.data, folder="resumes", suffix=upload.extension)
    )
    primary = await _current_primary(session)
    # The profile is the user's own entry (PRD §14): start from the current primary's values.
    profile = CandidateProfile(
        **{f: getattr(primary.profile, f) for f in PROFILE_FIELDS} if primary else {}
    )
    label = sanitize_filename(name).strip() if name and name.strip() else None
    resume = Resume(
        name=(label or PurePosixPath(upload.display_name).stem)[:120],
        original_filename=upload.display_name,
        file_path=key,
        mime_type=upload.mime_type,
        size_bytes=len(upload.data),
        raw_text=text,
        text_hash=text_hash(text),
        is_primary=primary is None,
        profile=profile,
    )
    session.add(resume)
    try:
        await session.commit()
    except BaseException:
        await session.rollback()
        await to_thread.run_sync(storage.delete, key)
        raise
    logger.info(
        "resume_uploaded",
        extra={
            "event": "resume_uploaded",
            "resume_id": str(resume.id),
            "mime_type": resume.mime_type,
            "size_bytes": resume.size_bytes,
            "text_chars": len(text),
        },
    )
    return resume


async def list_resumes(session: AsyncSession) -> list[Resume]:
    rows = await session.execute(select(Resume).order_by(Resume.created_at.desc(), Resume.id))
    return list(rows.scalars())


async def get_resume(session: AsyncSession, resume_id: uuid.UUID) -> Resume | None:
    return await session.get(Resume, resume_id)


async def set_primary(session: AsyncSession, resume: Resume) -> Resume:
    await session.execute(
        update(Resume)
        .where(Resume.is_primary.is_(True), Resume.id != resume.id)
        .values(is_primary=False)
    )
    resume.is_primary = True
    await session.commit()
    await session.refresh(resume)
    return resume


async def delete_resume(session: AsyncSession, storage: StorageProvider, resume: Resume) -> None:
    """Delete the resume, its profile and its file (PRD §68). Promotes the newest remaining."""
    key, was_primary, resume_id = resume.file_path, resume.is_primary, resume.id
    await session.delete(resume)
    await session.flush()
    if was_primary:
        newest = await session.scalar(
            select(Resume).order_by(Resume.created_at.desc(), Resume.id).limit(1)
        )
        if newest is not None:
            newest.is_primary = True
    await session.commit()
    try:
        await to_thread.run_sync(storage.delete, key)
    except OSError:
        logger.warning(
            "resume_file_delete_failed",
            extra={"event": "resume_file_delete_failed", "resume_id": str(resume_id)},
        )
    logger.info("resume_deleted", extra={"event": "resume_deleted", "resume_id": str(resume_id)})


LIST_FIELDS = {f for f in PROFILE_FIELDS if f not in ("years_experience", "remote_preference")}


async def update_profile(
    session: AsyncSession, profile: CandidateProfile, changes: CandidateProfileUpdate
) -> CandidateProfile:
    for field in changes.model_fields_set:
        value = getattr(changes, field)
        if field == "languages":
            value = [entry.model_dump() for entry in value or []]
        elif field in LIST_FIELDS and value is None:
            value = []  # lists are cleared, never null
        setattr(profile, field, value)
    await session.commit()
    await session.refresh(profile)
    logger.info(
        "profile_updated",
        extra={
            "event": "profile_updated",
            "resume_id": str(profile.resume_id),
            "fields": sorted(changes.model_fields_set),
        },
    )
    return profile
