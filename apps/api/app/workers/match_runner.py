"""Runs one queued match with its own DB session (used by Celery and the inline queue)."""

import logging
import uuid

from app.core.config import get_settings
from app.db.session import standalone_session
from app.providers.decision import DecisionUnavailable
from app.providers.factory import get_decision_provider
from app.services import match_run_service, match_service

logger = logging.getLogger(__name__)


async def execute_match(match_id: uuid.UUID, *, retries_left: int) -> None:
    """Transport failures are re-raised while retries remain; afterwards the match fails."""
    async with standalone_session() as session:
        try:
            await match_service.run_match(session, get_decision_provider(), match_id)
        except DecisionUnavailable as exc:
            if retries_left > 0:
                raise
            await match_service.mark_failed(session, match_id, exc.code, exc.message)


async def execute_match_run(run_id: uuid.UUID) -> None:
    """Walk a batch run job by job; any unexpected crash fails the run instead of hanging it."""
    async with standalone_session() as session:
        try:
            await match_run_service.execute_run(
                session,
                get_decision_provider(),
                run_id,
                delays=get_settings().match_retry_delays_seconds,
            )
        except Exception as exc:
            logger.exception(
                "match_run_crashed", extra={"event": "match_run_crashed", "run_id": str(run_id)}
            )
            await session.rollback()
            await match_run_service.fail_run(session, run_id, "RUN_CRASHED", str(exc)[:300])
            raise
