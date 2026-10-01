import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import SessionDep
from app.connectors.factory import get_registry
from app.connectors.registry import ConnectorRegistry
from app.models import Job
from app.schemas.common import Page
from app.schemas.job import (
    JobImportResponse,
    JobImportTextRequest,
    JobImportUrlRequest,
    JobRead,
    JobSummary,
)
from app.services import job_import, job_service
from app.services.job_import import CompanyNotFound, ImportResult, SnapshotConflict

router = APIRouter(prefix="/jobs", tags=["jobs"])

RegistryDep = Annotated[ConnectorRegistry, Depends(get_registry)]


def _response(result: ImportResult) -> JobImportResponse:
    return JobImportResponse(outcome=result.outcome, job=JobRead.model_validate(result.job))


@router.post("/import-url", response_model=JobImportResponse)
async def import_url(
    body: JobImportUrlRequest, session: SessionDep, registry: RegistryDep
) -> JobImportResponse:
    """Import one vacancy from its original employer/ATS URL (never EURES)."""
    try:
        result = await job_import.import_from_url(
            session, registry, body.url, company_id=body.company_id
        )
    except CompanyNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _response(result)


@router.post("/import-text", response_model=JobImportResponse)
async def import_text(body: JobImportTextRequest, session: SessionDep) -> JobImportResponse:
    """Manual JD paste for pages that cannot be retrieved automatically."""
    try:
        result = await job_import.import_manual(
            session,
            title=body.title,
            description=body.description,
            employer_name=body.employer_name,
            location=body.location,
            source_url=body.source_url,
            apply_url=body.apply_url,
            company_id=body.company_id,
        )
    except CompanyNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _response(result)


@router.get("", response_model=Page[JobSummary])
async def list_jobs(
    session: SessionDep,
    company_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[JobSummary]:
    items, total = await job_service.list_jobs(
        session, company_id=company_id, q=q, page=page, page_size=page_size
    )
    return Page(
        items=[JobSummary.model_validate(j) for j in items],
        total=total,
        page=page,
        page_size=page_size,
    )


async def _job_or_404(session: SessionDep, job_id: uuid.UUID) -> Job:
    try:
        return await job_import.load_job(session, job_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found") from exc


@router.get("/{job_id}", response_model=JobRead)
async def get_job(job_id: uuid.UUID, session: SessionDep) -> JobRead:
    return JobRead.model_validate(await _job_or_404(session, job_id))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: uuid.UUID, session: SessionDep) -> Response:
    job = await _job_or_404(session, job_id)
    await session.delete(job)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{job_id}/sources/{source_id}/accept", response_model=JobRead)
async def accept_source_update(
    job_id: uuid.UUID, source_id: uuid.UUID, session: SessionDep
) -> JobRead:
    return await _review(session, job_id, source_id, accept=True)


@router.post("/{job_id}/sources/{source_id}/reject", response_model=JobRead)
async def reject_source_update(
    job_id: uuid.UUID, source_id: uuid.UUID, session: SessionDep
) -> JobRead:
    return await _review(session, job_id, source_id, accept=False)


async def _review(
    session: SessionDep, job_id: uuid.UUID, source_id: uuid.UUID, *, accept: bool
) -> JobRead:
    job = await _job_or_404(session, job_id)
    try:
        job = await job_import.review_snapshot(session, job, source_id, accept=accept)
    except SnapshotConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return JobRead.model_validate(job)
