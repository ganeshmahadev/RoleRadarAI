"""Where queued matches run (PRD §44, §69: scoring never blocks the request)."""

import asyncio
import logging
import uuid
from collections.abc import Coroutine
from typing import Any, Protocol

from anyio import to_thread

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


class QueueUnavailable(AppError):
    code = "QUEUE_UNAVAILABLE"
    retryable = True
    http_status = 503


class MatchQueue(Protocol):
    async def enqueue(self, match_id: uuid.UUID) -> None: ...

    async def enqueue_run(self, run_id: uuid.UUID) -> None: ...

    async def enqueue_discovery(self, run_id: uuid.UUID) -> None: ...


class CeleryMatchQueue:
    async def _send(self, task: str, arg: uuid.UUID) -> None:
        from app.workers.celery_app import celery_app

        try:
            await to_thread.run_sync(lambda: celery_app.send_task(task, args=[str(arg)]))
        except Exception as exc:  # broker down, connection refused, ...
            raise QueueUnavailable("The background worker queue (Redis) is not reachable") from exc

    async def enqueue(self, match_id: uuid.UUID) -> None:
        await self._send("roleradar.score_match", match_id)

    async def enqueue_run(self, run_id: uuid.UUID) -> None:
        await self._send("roleradar.match_run", run_id)

    async def enqueue_discovery(self, run_id: uuid.UUID) -> None:
        await self._send("roleradar.discovery_run", run_id)


class InlineMatchQueue:
    """Runs matches as asyncio tasks in the API process (tests, worker-less local runs)."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def enqueue(self, match_id: uuid.UUID) -> None:
        from app.workers.match_runner import execute_match

        self._spawn(execute_match(match_id, retries_left=0))

    async def enqueue_run(self, run_id: uuid.UUID) -> None:
        from app.workers.match_runner import execute_match_run

        self._spawn(execute_match_run(run_id))

    async def enqueue_discovery(self, run_id: uuid.UUID) -> None:
        from app.workers.match_runner import execute_discovery_run

        self._spawn(execute_discovery_run(run_id))

    async def drain(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)


_inline = InlineMatchQueue()


def get_match_queue() -> MatchQueue:
    return _inline if get_settings().match_queue == "inline" else CeleryMatchQueue()
