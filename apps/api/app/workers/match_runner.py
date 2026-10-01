"""Runs one queued match with its own DB session (used by Celery and the inline queue)."""

import logging
import uuid

from app.core.config import get_settings
from app.db.session import standalone_session
from app.discovery.eures_scan import EuresClient
from app.discovery.jobspy_source import JobSpyClient, LiveJobSpyClient
from app.providers.decision import DecisionUnavailable
from app.providers.factory import get_decision_provider
from app.services import discovery_service, match_run_service, match_service

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


def jobspy_client() -> JobSpyClient | None:
    """None when job-board discovery is off (PRD §84 guardrail: off by default)."""
    settings = get_settings()
    if not settings.discovery_jobspy_enabled:
        return None
    if settings.discovery_sources == "fake":
        from tests.fake_jobspy import FakeJobSpyClient  # deterministic E2E data

        return FakeJobSpyClient()
    return LiveJobSpyClient()


def eures_client() -> EuresClient | None:
    """None unless EURES_SCRAPER_ENABLED (PRD §84 user override; off by default)."""
    settings = get_settings()
    if not settings.eures_scraper_enabled:
        return None
    if settings.discovery_sources == "fake":
        from tests.fake_eures import handler  # offline fixtures for E2E

        return EuresClient(crawl_delay=0, transport=handler())
    return EuresClient(crawl_delay=max(settings.eures_crawl_delay_seconds, 10.0))


async def execute_discovery_run(run_id: uuid.UUID) -> None:
    settings = get_settings()
    async with standalone_session() as session:
        try:
            await discovery_service.execute_run(
                session,
                run_id,
                client=jobspy_client(),
                provider=get_decision_provider(),
                eures=eures_client(),
                delays=settings.match_retry_delays_seconds,
                pause_seconds=settings.discovery_pause_seconds,
            )
        except Exception as exc:
            logger.exception(
                "discovery_run_crashed",
                extra={"event": "discovery_run_crashed", "run_id": str(run_id)},
            )
            await session.rollback()
            await discovery_service.fail_run(session, run_id, "RUN_CRASHED", str(exc)[:300])
            raise
