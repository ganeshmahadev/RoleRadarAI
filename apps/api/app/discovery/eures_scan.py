"""EURES scan (PRD §84) — user override for local educational/testing use. Off by default.

Endpoints and payload confirmed by the user from their browser (OD-7, 2026-10-02):
  POST {SEARCH_URL}  body = search_payload(...)  → {"numberRecords", "jvs": [...]}
  GET  {DETAIL_URL}  → {"jvProfiles": {lang: {..., "employer": {"legalID": <CVR>}}}}

Guardrails: one request at a time with at least the robots.txt Crawl-delay (10 s) between
requests; an honest User-Agent; HTTP 403/429 or a non-JSON answer (e.g. a captcha page) stops
the scan as "blocked" — never retried, never worked around.
"""

import asyncio
import re
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.connectors.base import NormalizedJob
from app.connectors.text import clean_text, html_to_text
from app.models import SourceType
from app.services.company_normalization import normalize_company_name, normalize_text

SEARCH_URL = "https://europa.eu/eures/api/jv-searchengine/public/jv-search/search"
DETAIL_URL = "https://europa.eu/eures/api/jv-searchengine/public/jv/id/{id}?requestLang=en&preferredLang=null"
USER_AGENT = (
    "RoleRadarAI/0.1 (personal job-search research; local use; robots Crawl-delay honoured)"
)
PAGE_SIZE = 50
_HREF = re.compile(r'href="(https?://[^"]+)"')


class EuresBlocked(Exception):
    """403/429/captcha: stop the scan for this run (no retries, no evasion)."""


class EuresError(Exception):
    """A transient or unexpected failure for one request."""


def search_payload(keyword: str, *, page: int, session_id: str) -> dict[str, Any]:
    """Exactly the body the EURES web app sends (only keyword/page/session vary)."""
    return {
        "resultsPerPage": PAGE_SIZE,
        "page": page,
        "sortSearch": "BEST_MATCH",
        "keywords": [{"keyword": keyword, "specificSearchCode": "EVERYWHERE"}],
        "publicationPeriod": "LAST_MONTH",
        "occupationUris": [],
        "skillUris": [],
        "requiredExperienceCodes": [],
        "positionScheduleCodes": [],
        "sectorCodes": [],
        "educationAndQualificationLevelCodes": [],
        "positionOfferingCodes": [],
        "locationCodes": ["dk"],
        "euresFlagCodes": [],
        "otherBenefitsCodes": [],
        "requiredLanguages": [],
        "minNumberPost": None,
        "sessionId": session_id,
        "requestLanguage": "en",
        "userPreferredLanguage": None,
    }


class EuresClient:
    def __init__(
        self,
        *,
        crawl_delay: float,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._delay = crawl_delay
        self._transport = transport
        self._sleep = sleep
        self._monotonic = monotonic
        self._last: float | None = None
        self.session_id = secrets.token_hex(11)
        self.requests = 0

    async def _throttle(self) -> None:
        if self._last is not None:
            wait = self._delay - (self._monotonic() - self._last)
            if wait > 0:
                await self._sleep(wait)
        self._last = self._monotonic()

    async def _request(self, method: str, url: str, body: dict[str, Any] | None = None) -> Any:
        await self._throttle()
        self.requests += 1
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=httpx.Timeout(30.0, connect=10.0)
            ) as client:
                response = await client.request(method, url, json=body, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise EuresError(f"EURES request failed: {type(exc).__name__}") from exc
        if response.status_code in (403, 429):
            raise EuresBlocked(f"EURES answered HTTP {response.status_code}")
        if response.status_code >= 400:
            raise EuresError(f"EURES answered HTTP {response.status_code}")
        if "json" not in response.headers.get("content-type", ""):
            raise EuresBlocked("EURES returned a non-JSON page (possibly a captcha)")
        try:
            return response.json()
        except ValueError as exc:
            raise EuresBlocked("EURES returned invalid JSON") from exc

    async def search(self, keyword: str, *, page: int = 1) -> dict[str, Any]:
        data = await self._request(
            "POST", SEARCH_URL, search_payload(keyword, page=page, session_id=self.session_id)
        )
        if not isinstance(data, dict) or not isinstance(data.get("jvs"), list):
            raise EuresError("Unexpected EURES search response")
        return data

    async def detail(self, job_id: str) -> dict[str, Any]:
        data = await self._request("GET", DETAIL_URL.format(id=job_id))
        if not isinstance(data, dict) or not isinstance(data.get("jvProfiles"), dict):
            raise EuresError("Unexpected EURES detail response")
        return data


@dataclass(frozen=True)
class Hit:
    id: str
    title: str
    description_html: str
    employer_name: str | None
    created: datetime | None
    eures_flag: bool
    raw: dict[str, Any]


def _ms(value: object) -> datetime | None:
    return datetime.fromtimestamp(value / 1000, tz=UTC) if isinstance(value, (int, float)) else None


def parse_hits(data: dict[str, Any]) -> list[Hit]:
    hits: list[Hit] = []
    for raw in data.get("jvs", []):
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        translations = raw.get("translations") or {}
        text: dict[str, Any] = (
            next(iter(translations.values()), {}) if isinstance(translations, dict) else {}
        )
        title = clean_text(text.get("title") or raw.get("title"))
        description = text.get("description") or raw.get("description") or ""
        if not title:
            continue
        employer = raw.get("employer") or {}
        hits.append(
            Hit(
                id=str(raw["id"]),
                title=title,
                description_html=description if isinstance(description, str) else "",
                employer_name=clean_text(employer.get("name"))
                if isinstance(employer, dict)
                else None,
                created=_ms(raw.get("creationDate")),
                eures_flag=bool(raw.get("euresFlag")),
                raw=raw,
            )
        )
    return hits


def dedupe(hits: list[Hit]) -> list[Hit]:
    """EURES lists some vacancies twice (national feed + English copy): keep one per
    employer + title, preferring the EURES-flagged original."""
    seen: set[tuple[str, str]] = set()
    unique: list[Hit] = []
    for hit in sorted(hits, key=lambda h: not h.eures_flag):
        key = (normalize_company_name(hit.employer_name or ""), normalize_text(hit.title))
        if key not in seen:
            seen.add(key)
            unique.append(hit)
    return unique


def employer_matches(hit: Hit, normalized_company_name: str) -> bool:
    return (
        bool(hit.employer_name)
        and normalize_company_name(hit.employer_name or "") == normalized_company_name
    )


def _profile(detail: dict[str, Any] | None) -> dict[str, Any]:
    if not detail:
        return {}
    profiles = detail.get("jvProfiles") or {}
    return next(iter(profiles.values()), {}) if isinstance(profiles, dict) else {}


def legal_id(detail: dict[str, Any]) -> str | None:
    """The employer's CVR as published by EURES (only in the detail response)."""
    employer = _profile(detail).get("employer") or {}
    value = employer.get("legalID") if isinstance(employer, dict) else None
    return str(value).strip() if value else None


def _apply_link(*html: str) -> str | None:
    for chunk in html:
        for url in _HREF.findall(chunk or ""):
            if "europa.eu" not in url:
                return str(url)
    return None


def to_job(hit: Hit, detail: dict[str, Any] | None = None) -> NormalizedJob:
    profile = _profile(detail)
    instructions = " ".join(
        i for i in profile.get("applicationInstructions", []) if isinstance(i, str)
    )
    city = None
    locations = profile.get("locations") or []
    if locations and isinstance(locations[0], dict):
        city = clean_text(locations[0].get("cityName"))
    description = html_to_text(profile.get("description") or hit.description_html)
    source = DETAIL_URL.format(id=hit.id)
    return NormalizedJob(
        source_type=SourceType.EURES,
        source_url=source,
        final_url=source,
        title=hit.title,
        description=description,
        employer_name=hit.employer_name,
        location=f"{city}, Denmark" if city else "Denmark",
        country="Denmark",
        city=city,
        apply_url=_apply_link(instructions, hit.description_html),
        external_job_id=hit.id,
        published_at=hit.created,
    )
