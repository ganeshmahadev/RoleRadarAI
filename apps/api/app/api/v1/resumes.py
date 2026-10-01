import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.models import Resume
from app.providers.storage import LocalStorageProvider, StorageProvider
from app.schemas.profile import CandidateProfileRead, CandidateProfileUpdate
from app.schemas.resume import ResumeRead, ResumeSummary
from app.services import resume_service
from app.services.resume_files import MAX_UPLOAD_BYTES
from app.services.resume_parser import DefaultResumeParser, ResumeParser

router = APIRouter(prefix="/resumes", tags=["resumes"])


@lru_cache
def get_storage() -> StorageProvider:
    return LocalStorageProvider(get_settings().upload_dir)


def get_parser() -> ResumeParser:
    return DefaultResumeParser()


StorageDep = Annotated[StorageProvider, Depends(get_storage)]
ParserDep = Annotated[ResumeParser, Depends(get_parser)]


def _summary(resume: Resume) -> ResumeSummary:
    return ResumeSummary.model_validate(resume)


def _read(resume: Resume) -> ResumeRead:
    return ResumeRead.model_validate(resume)


async def _resume_or_404(session: SessionDep, resume_id: uuid.UUID) -> Resume:
    resume = await resume_service.get_resume(session, resume_id)
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return resume


@router.post("", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    session: SessionDep,
    storage: StorageDep,
    parser: ParserDep,
    file: Annotated[UploadFile, File(description="PDF, DOCX or TXT, at most 10 MB")],
    name: Annotated[str | None, Form(max_length=120)] = None,
) -> ResumeRead:
    data = await file.read(MAX_UPLOAD_BYTES + 1)  # one extra byte detects oversize files
    resume = await resume_service.create_resume(
        session, storage, parser, filename=file.filename, data=data, name=name
    )
    return _read(resume)


@router.get("", response_model=list[ResumeSummary])
async def list_resumes(session: SessionDep) -> list[ResumeSummary]:
    return [_summary(r) for r in await resume_service.list_resumes(session)]


@router.get("/{resume_id}", response_model=ResumeRead)
async def get_resume(resume_id: uuid.UUID, session: SessionDep) -> ResumeRead:
    return _read(await _resume_or_404(session, resume_id))


@router.post("/{resume_id}/set-primary", response_model=ResumeSummary)
async def set_primary(resume_id: uuid.UUID, session: SessionDep) -> ResumeSummary:
    resume = await _resume_or_404(session, resume_id)
    return _summary(await resume_service.set_primary(session, resume))


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(resume_id: uuid.UUID, session: SessionDep, storage: StorageDep) -> Response:
    await resume_service.delete_resume(session, storage, await _resume_or_404(session, resume_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{resume_id}/profile", response_model=CandidateProfileRead)
async def get_profile(resume_id: uuid.UUID, session: SessionDep) -> CandidateProfileRead:
    resume = await _resume_or_404(session, resume_id)
    return CandidateProfileRead.model_validate(resume.profile)


@router.patch("/{resume_id}/profile", response_model=CandidateProfileRead)
async def update_profile(
    resume_id: uuid.UUID, body: CandidateProfileUpdate, session: SessionDep
) -> CandidateProfileRead:
    resume = await _resume_or_404(session, resume_id)
    profile = await resume_service.update_profile(session, resume.profile, body)
    return CandidateProfileRead.model_validate(profile)
