import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import SessionDep
from app.models import Company, EuresStatus
from app.schemas.common import Page
from app.schemas.company import CompanyRead, CompanySort
from app.schemas.eures import CompanyUpdate, EuresSearch
from app.services import company_service, eures_workflow
from app.services.company_service import CompanyFilters

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=Page[CompanyRead])
async def list_companies(
    session: SessionDep,
    q: Annotated[
        str | None, Query(max_length=200, description="Name, normalized name or CVR")
    ] = None,
    eures_status: Annotated[list[EuresStatus] | None, Query()] = None,
    checked: Annotated[bool | None, Query(description="EURES review reached an outcome")] = None,
    siri_certified: bool | None = None,
    sort: CompanySort = "position",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[CompanyRead]:
    filters = CompanyFilters(
        q=q, eures_status=eures_status or [], checked=checked, siri_certified=siri_certified
    )
    items, total = await company_service.list_companies(
        session, filters, page=page, page_size=page_size, sort=sort
    )
    return Page(
        items=[CompanyRead.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


async def _get_or_404(session: SessionDep, company_id: uuid.UUID) -> Company:
    company = await company_service.get_company(session, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(company_id: uuid.UUID, session: SessionDep) -> CompanyRead:
    return CompanyRead.model_validate(await _get_or_404(session, company_id))


@router.patch("/{company_id}", response_model=CompanyRead)
async def update_company(
    company_id: uuid.UUID, body: CompanyUpdate, session: SessionDep
) -> CompanyRead:
    company = await _get_or_404(session, company_id)
    if "eures_notes" in body.model_fields_set:
        company = await eures_workflow.update_notes(session, company, body.eures_notes)
    return CompanyRead.model_validate(company)


@router.get("/{company_id}/eures-search", response_model=EuresSearch)
async def eures_search(company_id: uuid.UUID, session: SessionDep) -> EuresSearch:
    company = await _get_or_404(session, company_id)
    return EuresSearch(
        company_id=company.id,
        company_name=company.company_name,
        url=company.eures_search_url,
        status=company.eures_status,
    )


@router.post("/{company_id}/eures-opened", response_model=CompanyRead)
async def eures_opened(company_id: uuid.UUID, session: SessionDep) -> CompanyRead:
    """NOT_CHECKED → OPENED; completed statuses are left unchanged."""
    company = await eures_workflow.mark_opened(session, await _get_or_404(session, company_id))
    return CompanyRead.model_validate(company)


@router.post("/{company_id}/mark-no-jobs", response_model=CompanyRead)
async def mark_no_jobs(company_id: uuid.UUID, session: SessionDep) -> CompanyRead:
    """Checked on EURES, no relevant jobs (= "Mark checked" / "Mark complete", PRD §8)."""
    company = await eures_workflow.mark_no_relevant_jobs(
        session, await _get_or_404(session, company_id)
    )
    return CompanyRead.model_validate(company)


@router.post("/{company_id}/mark-eures-error", response_model=CompanyRead)
async def mark_eures_error(company_id: uuid.UUID, session: SessionDep) -> CompanyRead:
    company = await eures_workflow.mark_error(session, await _get_or_404(session, company_id))
    return CompanyRead.model_validate(company)


@router.post("/{company_id}/reset-eures", response_model=CompanyRead)
async def reset_eures(company_id: uuid.UUID, session: SessionDep) -> CompanyRead:
    company = await eures_workflow.reset(session, await _get_or_404(session, company_id))
    return CompanyRead.model_validate(company)
