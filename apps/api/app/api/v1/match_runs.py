import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.models import MatchRun
from app.schemas.match_run import PlannedJobRead, RunItemRead, RunPlanRead, RunRead, RunRequest
from app.services import match_run_service
from app.services.match_queue import MatchQueue, get_match_queue

router = APIRouter(prefix="/match-runs", tags=["match runs"])

QueueDep = Annotated[MatchQueue, Depends(get_match_queue)]
TERMINAL = {"DONE", "CANCELLED", "FAILED"}
KEEPALIVE_SECONDS = 15.0


async def to_read(session: AsyncSession, run: MatchRun) -> RunRead:
    progress = await match_run_service.progress(session, run)
    current = next((i for i in run.items if i.job_id == run.current_job_id), None)
    return RunRead(
        id=run.id,
        status=run.status,
        scope=run.scope,
        relevance_filter=run.relevance_filter,
        target_roles=run.target_roles,
        counts=progress.counts,
        finished=progress.finished,
        total=progress.total,
        current_job_id=run.current_job_id,
        current_job_title=current.job_title if current else None,
        seconds_per_job=progress.seconds_per_job,
        seconds_remaining=progress.seconds_remaining,
        error_code=run.error_code,
        error_message=run.error_message,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        items=[RunItemRead.model_validate(i) for i in run.items],
    )


def _planned(jobs: list[match_run_service.PlannedJob]) -> list[PlannedJobRead]:
    return [
        PlannedJobRead(job_id=j.job_id, title=j.title, matched_role=j.matched_role) for j in jobs
    ]


@router.post("/preview", response_model=RunPlanRead)
async def preview_run(body: RunRequest, session: SessionDep) -> RunPlanRead:
    """What a run would score and skip, without starting it."""
    plan = await match_run_service.plan_run(
        session,
        scope=body.scope,
        job_ids=body.job_ids,
        apply_relevance_filter=body.apply_relevance_filter,
    )
    return RunPlanRead(
        scope=plan.scope,
        relevance_filter=plan.relevance_filter,
        target_roles=plan.target_roles,
        to_score=_planned(plan.to_score),
        not_relevant=_planned(plan.not_relevant),
        seconds_per_job=await match_run_service.average_scoring_seconds(session),
    )


@router.post("", response_model=RunRead, status_code=status.HTTP_202_ACCEPTED)
async def start_run(body: RunRequest, session: SessionDep, queue: QueueDep) -> RunRead:
    """Returns immediately with status QUEUED (PRD §44); follow /match-runs/{id}/events."""
    plan = await match_run_service.plan_run(
        session,
        scope=body.scope,
        job_ids=body.job_ids,
        apply_relevance_filter=body.apply_relevance_filter,
    )
    run = await match_run_service.create_run(session, plan)
    try:
        await queue.enqueue_run(run.id)
    except Exception:
        await match_run_service.fail_run(
            session, run.id, "QUEUE_UNAVAILABLE", "Could not queue the run"
        )
        raise
    return await to_read(session, run)


@router.get("", response_model=list[RunRead])
async def list_runs(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=50)] = 5
) -> list[RunRead]:
    return [
        await to_read(session, run)
        for run in await match_run_service.list_runs(session, limit=limit)
    ]


@router.get("/{run_id}", response_model=RunRead)
async def get_run(run_id: uuid.UUID, session: SessionDep) -> RunRead:
    return await to_read(session, await match_run_service.get_run(session, run_id))


@router.post("/{run_id}/cancel", response_model=RunRead)
async def cancel_run(run_id: uuid.UUID, session: SessionDep) -> RunRead:
    run = await match_run_service.cancel_run(
        session, await match_run_service.get_run(session, run_id)
    )
    return await to_read(session, run)


@router.get("/{run_id}/events")
async def run_events(run_id: uuid.UUID, session: SessionDep) -> Response:
    """Server-Sent Events (PRD §44): `progress` whenever the run changes, then `end`."""
    await match_run_service.get_run(session, run_id)  # 404 before streaming
    poll = get_settings().run_events_poll_seconds

    async def stream() -> AsyncIterator[str]:
        last: str | None = None
        quiet = 0.0
        while True:
            async with get_sessionmaker()() as s:
                run = await match_run_service.get_run(s, run_id)
                data = (await to_read(s, run)).model_dump_json()
                done = run.status.value in TERMINAL
            if data != last:
                yield f"event: progress\ndata: {data}\n\n"
                last, quiet = data, 0.0
            elif quiet >= KEEPALIVE_SECONDS:
                yield ": keepalive\n\n"
                quiet = 0.0
            if done:
                yield "event: end\ndata: {}\n\n"
                return
            await asyncio.sleep(poll)
            quiet += poll

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
