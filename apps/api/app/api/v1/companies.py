import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import SessionDep
from app.models import EuresStatus
from app.schemas.common import Page
from app.schemas.company import CompanyRead, CompanySort
from app.services import company_service
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


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(company_id: uuid.UUID, session: SessionDep) -> CompanyRead:
    company = await company_service.get_company(session, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Company not found")
    return CompanyRead.model_validate(company)
