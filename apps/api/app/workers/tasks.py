import asyncio
import uuid

from celery import Task

from app.providers.decision import DecisionUnavailable
from app.workers.celery_app import celery_app
from app.workers.match_runner import execute_match, execute_match_run

MAX_RETRIES = 2


@celery_app.task(
    name="roleradar.score_match",
    bind=True,
    max_retries=MAX_RETRIES,
    acks_late=True,
    soft_time_limit=3500,
    time_limit=3600,
)
def score_match(self: Task, match_id: str) -> None:  # type: ignore[type-arg]
    """Score one match; OpenJev being down is retried with backoff (PRD §57)."""
    try:
        asyncio.run(
            execute_match(uuid.UUID(match_id), retries_left=MAX_RETRIES - self.request.retries)
        )
    except DecisionUnavailable as exc:
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1)) from exc


@celery_app.task(name="roleradar.match_run", acks_late=False)  # no time limit: runs can be long
def match_run(run_id: str) -> None:
    """Walk a batch run sequentially. Not acks_late: a redelivery would start a second walker."""
    asyncio.run(execute_match_run(uuid.UUID(run_id)))
