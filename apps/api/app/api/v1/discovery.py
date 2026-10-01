import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.api.v1.match_runs import to_read as match_run_read
from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.models import DiscoveryRun, MatchRun
from app.schemas.discovery import (
    DiscoveryRunRead,
    DiscoveryRunRequest,
    DiscoverySettingsRead,
    DiscoverySettingsUpdate,
)
from app.services import discovery_service
from app.services.match_queue import MatchQueue, get_match_queue

router = APIRouter(tags=["discovery"])
QueueDep = Annotated[MatchQueue, Depends(get_match_queue)]
TERMINAL = {"DONE", "CANCELLED", "FAILED"}
EURES_AVAILABLE = False  # until the EURES search request format is confirmed (OD-7)


async def settings_read(session: AsyncSession) -> DiscoverySettingsRead:
    row = await discovery_service.get_settings_row(session)
    config = get_settings()
    base = DiscoverySettingsRead.model_validate(row)
    return base.model_copy(
        update={
            "effective_terms": await discovery_service.effective_terms(session, row),
            "jobspy_enabled": config.discovery_jobspy_enabled,
            "eures_scraper_enabled": config.eures_scraper_enabled,
            "eures_available": EURES_AVAILABLE,
        }
    )


async def run_read(session: AsyncSession, run: DiscoveryRun) -> DiscoveryRunRead:
    scoring = None
    if run.match_run_id:
        match_run = await session.get(MatchRun, run.match_run_id, populate_existing=True)
        if match_run is not None:
            scoring = await match_run_read(session, match_run)
    return DiscoveryRunRead(
        id=run.id,
        trigger=run.trigger,
        status=run.status,
        phase=run.phase,
        settings=run.settings,
        sources=run.sources,
        new_jobs=run.new_jobs,
        scoring=scoring,
        error_code=run.error_code,
        error_message=run.error_message,
        created_at=run.created_at,
        started_at=run.started_at,
        scrape_deadline=run.scrape_deadline,
        deadline=run.deadline,
        completed_at=run.completed_at,
    )


@router.get("/discovery/settings", response_model=DiscoverySettingsRead)
async def get_discovery_settings(session: SessionDep) -> DiscoverySettingsRead:
    return await settings_read(session)


@router.put("/discovery/settings", response_model=DiscoverySettingsRead)
async def update_discovery_settings(
    body: DiscoverySettingsUpdate, session: SessionDep
) -> DiscoverySettingsRead:
    row = await discovery_service.get_settings_row(session)
    changes = {k: getattr(body, k) for k in body.model_fields_set if getattr(body, k) is not None}
    await discovery_service.update_settings(session, row, changes)
    return await settings_read(session)


@router.post(
    "/discovery-runs", response_model=DiscoveryRunRead, status_code=status.HTTP_202_ACCEPTED
)
async def start_discovery(
    session: SessionDep, queue: QueueDep, body: DiscoveryRunRequest | None = None
) -> DiscoveryRunRead:
    """ "Search now" or the daily trigger: returns immediately (QUEUED)."""
    run = await discovery_service.create_run(session, (body or DiscoveryRunRequest()).trigger)
    try:
        await queue.enqueue_discovery(run.id)
    except Exception:
        await discovery_service.fail_run(
            session, run.id, "QUEUE_UNAVAILABLE", "Could not queue the run"
        )
        raise
    return await run_read(session, run)


@router.get("/discovery-runs", response_model=list[DiscoveryRunRead])
async def list_discovery_runs(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=50)] = 5
) -> list[DiscoveryRunRead]:
    return [
        await run_read(session, r) for r in await discovery_service.list_runs(session, limit=limit)
    ]


@router.get("/discovery-runs/{run_id}", response_model=DiscoveryRunRead)
async def get_discovery_run(run_id: uuid.UUID, session: SessionDep) -> DiscoveryRunRead:
    return await run_read(session, await discovery_service.get_run(session, run_id))


@router.post("/discovery-runs/{run_id}/cancel", response_model=DiscoveryRunRead)
async def cancel_discovery_run(run_id: uuid.UUID, session: SessionDep) -> DiscoveryRunRead:
    run = await discovery_service.cancel_run(
        session, await discovery_service.get_run(session, run_id)
    )
    return await run_read(session, run)


@router.get("/discovery-runs/{run_id}/events")
async def discovery_events(run_id: uuid.UUID, session: SessionDep) -> Response:
    """SSE: `progress` whenever the run (or its scoring batch) changes, then `end`."""
    await discovery_service.get_run(session, run_id)
    poll = get_settings().run_events_poll_seconds

    async def stream() -> AsyncIterator[str]:
        last: str | None = None
        while True:
            async with get_sessionmaker()() as s:
                run = await discovery_service.get_run(s, run_id)
                data = (await run_read(s, run)).model_dump_json()
                done = run.status.value in TERMINAL
            if data != last:
                yield f"event: progress\ndata: {data}\n\n"
                last = data
            if done:
                yield "event: end\ndata: {}\n\n"
                return
            await asyncio.sleep(poll)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
