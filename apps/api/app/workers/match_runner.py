"""Runs one queued match with its own DB session (used by Celery and the inline queue)."""

import logging
import uuid

from app.db.session import standalone_session
from app.providers.decision import DecisionUnavailable
from app.providers.factory import get_decision_provider
from app.services import match_service

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
