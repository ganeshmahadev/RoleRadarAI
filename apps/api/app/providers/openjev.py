"""OpenJevProvider: the local OpenJev MLX server (PRD §11.1, §29; contract confirmed in §29).

Talks to a configured internal URL, so it does NOT go through the SSRF-guarded job fetcher.
Retries only transport failures (PRD §29); the server is single-user and local.
"""

import asyncio
import hashlib
import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.providers.decision import (
    DecisionInvalidResponse,
    DecisionRequestRejected,
    DecisionResult,
    DecisionUnavailable,
    ModelInfo,
    Question,
)

logger = logging.getLogger(__name__)

TRANSPORT_RETRIES = 2
RETRY_BACKOFF_SECONDS = 2.0


class _Version(BaseModel):
    model_dir: str
    T: float
    noul_t: float
    noul_bias: float
    flags: dict[str, Any]
    shim_sha256: str


def revision_from_version(data: dict[str, Any]) -> ModelInfo:
    v = _Version.model_validate(data)
    flags = hashlib.sha256(json.dumps(v.flags, sort_keys=True).encode()).hexdigest()[:8]
    revision = (
        f"{v.model_dir};T={v.T};noul={v.noul_t},{v.noul_bias};"
        f"helper={v.shim_sha256[:12]};flags={flags}"
    )
    return ModelInfo(provider="openjev", name=v.model_dir, revision=revision)


class OpenJevProvider:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
        backoff_seconds: float = RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds, connect=5.0)
        self._transport = transport
        self._backoff = backoff_seconds

    async def _request(self, method: str, path: str, body: Any = None) -> Any:
        last_error: Exception | None = None
        for attempt in range(TRANSPORT_RETRIES + 1):
            if attempt:
                await asyncio.sleep(self._backoff * attempt)
            try:
                async with httpx.AsyncClient(
                    base_url=self._base_url, timeout=self._timeout, transport=self._transport
                ) as client:
                    response = await client.request(method, path, json=body)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                logger.warning(
                    "openjev_transport_error",
                    extra={"event": "openjev_transport_error", "attempt": attempt + 1},
                )
                continue
            if response.status_code >= 500:
                raise DecisionUnavailable(f"OpenJev returned HTTP {response.status_code}")
            if response.status_code >= 400:
                raise DecisionRequestRejected(
                    f"OpenJev rejected the request: {response.text[:200]}"
                )
            try:
                return response.json()
            except ValueError as exc:
                raise DecisionInvalidResponse("OpenJev returned invalid JSON") from exc
        raise DecisionUnavailable(
            "OpenJev is not reachable. Start it with ~/models/openjev/start-openjev.sh"
        ) from last_error

    async def model_info(self) -> ModelInfo:
        data = await self._request("GET", "/v1/version")
        try:
            return revision_from_version(data)
        except ValidationError as exc:
            raise DecisionInvalidResponse("Unexpected /v1/version response") from exc

    async def decide(self, state: str, questions: dict[str, Question]) -> DecisionResult:
        body = {"state": state, "questions": {k: q.model_dump() for k, q in questions.items()}}
        data = await self._request("POST", "/v1/systemone", body)
        try:
            result = DecisionResult.model_validate(
                {
                    "model": data["model"],
                    "answers": data["answers"],
                    "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                }
            )
        except (KeyError, TypeError, ValidationError) as exc:
            raise DecisionInvalidResponse("Unexpected /v1/systemone response") from exc
        missing = set(questions) - set(result.answers)
        mismatched = [
            k
            for k, q in questions.items()
            if k in result.answers and result.answers[k].type != q.type
        ]
        if missing or mismatched:
            raise DecisionInvalidResponse(
                "OpenJev answered incompletely "
                f"(missing {sorted(missing)}, wrong type {mismatched})"
            )
        return result
