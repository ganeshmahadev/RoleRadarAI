from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import SessionDep
from app.schemas.company import CompanyRead
from app.schemas.eures import EuresQueueStats
from app.services import eures_workflow

router = APIRouter(prefix="/eures", tags=["eures"])


@router.get("/stats", response_model=EuresQueueStats)
async def queue_stats(session: SessionDep) -> EuresQueueStats:
    stats = await eures_workflow.queue_stats(session)
    return EuresQueueStats(
        total=stats.total,
        checked=stats.checked,
        remaining=stats.remaining,
        by_status=stats.by_status,
    )


@router.get("/next-unchecked", response_model=CompanyRead)
async def next_unchecked(
    session: SessionDep,
    after_position: Annotated[int | None, Query(ge=0)] = None,
) -> CompanyRead:
    company = await eures_workflow.next_unchecked(session, after_position)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="All companies have been checked")
    return CompanyRead.model_validate(company)
