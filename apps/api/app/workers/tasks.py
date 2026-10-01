import asyncio
import uuid

from celery import Task

from app.providers.decision import DecisionUnavailable
from app.workers.celery_app import celery_app
from app.workers.match_runner import execute_match

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
