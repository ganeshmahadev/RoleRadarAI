import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import SessionDep
from app.models import MatchScore, MatchStatus
from app.providers.decision import DecisionProvider
from app.providers.factory import get_decision_provider
from app.schemas.match import Dimensions, MatchRead, ScoreRequest, ScoreResponse
from app.services import match_service
from app.services.match_queue import MatchQueue, get_match_queue

router = APIRouter(tags=["matches"])

ProviderDep = Annotated[DecisionProvider, Depends(get_decision_provider)]
QueueDep = Annotated[MatchQueue, Depends(get_match_queue)]


async def to_read(session: SessionDep, match: MatchScore) -> MatchRead:
    dims = Dimensions(
        must_have=match.must_have_fit,
        skills=match.skills_fit,
        experience=match.experience_fit,
        role=match.role_fit,
        seniority=match.seniority_fit,
        domain=match.domain_fit,
        education=match.education_fit,
    )
    computed = ("dimensions", "outdated")
    fields = {c: getattr(match, c) for c in MatchRead.model_fields if c not in computed}
    outdated = match.status is MatchStatus.DONE and await match_service.is_match_outdated(
        session, match
    )
    return MatchRead.model_validate({**fields, "dimensions": dims, "outdated": outdated})


@router.post("/jobs/{job_id}/score", response_model=ScoreResponse)
async def score_job(
    job_id: uuid.UUID,
    session: SessionDep,
    provider: ProviderDep,
    queue: QueueDep,
    response: Response,
    body: ScoreRequest | None = None,
) -> ScoreResponse:
    """Returns a cached or in-flight match (200) or queues a new one (202). Never waits for
    the model: poll GET /matches/{id} until status is DONE or FAILED."""
    match, created = await match_service.request_score(
        session, provider, job_id=job_id, resume_id=body.resume_id if body else None
    )
    if created:
        try:
            await queue.enqueue(match.id)
        except Exception:
            await match_service.mark_failed(
                session, match.id, "QUEUE_UNAVAILABLE", "Could not queue the scoring job"
            )
            raise
        response.status_code = status.HTTP_202_ACCEPTED
    return ScoreResponse(
        match=await to_read(session, match),
        cached=not created and match.status is MatchStatus.DONE,
    )


@router.get("/matches/{match_id}", response_model=MatchRead)
async def get_match(match_id: uuid.UUID, session: SessionDep) -> MatchRead:
    match = await match_service.get_match(session, match_id)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Match not found")
    return await to_read(session, match)


@router.get("/matches", response_model=list[MatchRead])
async def list_matches(
    session: SessionDep,
    job_id: uuid.UUID | None = None,
    resume_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[MatchRead]:
    matches = await match_service.list_matches(
        session, job_id=job_id, resume_id=resume_id, limit=limit
    )
    return [await to_read(session, m) for m in matches]
