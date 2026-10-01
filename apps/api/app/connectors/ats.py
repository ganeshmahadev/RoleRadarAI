"""Public ATS job-board APIs (PRD §26 priority 1).

Endpoints verified against live responses on 2026-10-01 (see BACKLOG P4-005..007).
These documented public APIs are meant for programmatic access, so the robots.txt
policy for generic pages does not apply. Values absent from the source stay None.
"""

import json
import re
from typing import Any
from urllib.parse import urlsplit

from app.connectors.base import ExternalJob, NormalizedJob, UrlImportConnector
from app.connectors.errors import ExtractionFailed, FetchFailed, UnsupportedSource
from app.connectors.http import SafeFetcher
from app.connectors.parse import first_str, parse_datetime
from app.connectors.text import clean_text, html_to_text
from app.models import SourceType

_UUID = r"[0-9a-fA-F-]{36}"


async def _get_json(fetcher: SafeFetcher, url: str) -> Any:
    response = await fetcher.get(url, accept="application/json")
    try:
        return json.loads(response.body)
    except ValueError as exc:
        raise FetchFailed("The ATS returned invalid JSON", retryable=False) from exc


def _require(title: str | None, description: str) -> str:
    if not title or not description:
        raise ExtractionFailed("The ATS posting has no title or description")
    return title


class GreenhouseConnector(UrlImportConnector):
    """job-boards.greenhouse.io/{board}/jobs/{id} → boards-api.greenhouse.io.

    EU-hosted boards (job-boards.eu.greenhouse.io) are not matched: their API host is
    unverified, so they fall through to the employer-page connector.
    """

    name = "greenhouse"
    _HOSTS = {"boards.greenhouse.io", "job-boards.greenhouse.io"}
    _PATH = re.compile(r"^/(?P<board>[A-Za-z0-9_-]+)/jobs/(?P<id>\d+)/?$")

    def __init__(self, fetcher: SafeFetcher) -> None:
        self._fetcher = fetcher

    def _match(self, url: str) -> re.Match[str] | None:
        parts = urlsplit(url)
        return self._PATH.match(parts.path) if parts.hostname in self._HOSTS else None

    def can_handle_url(self, url: str) -> bool:
        return self._match(url) is not None

    async def fetch_job_by_url(self, url: str) -> ExternalJob:
        match = self._match(url)
        if match is None:
            raise UnsupportedSource("Not a Greenhouse job URL")
        board, job_id = match["board"], match["id"]
        api = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
        return ExternalJob(
            SourceType.GREENHOUSE, url, url, job_id, await _get_json(self._fetcher, api)
        )

    async def normalize_job(self, external_job: ExternalJob) -> NormalizedJob:
        data = external_job.payload
        content = data.get("content")
        description = html_to_text(content, unescape_first=True) if isinstance(content, str) else ""
        location = data.get("location")
        return NormalizedJob(
            source_type=SourceType.GREENHOUSE,
            source_url=external_job.source_url,
            final_url=external_job.final_url,
            title=_require(clean_text(data.get("title")), description),
            description=description,
            employer_name=clean_text(data.get("company_name")),
            location=clean_text(location.get("name")) if isinstance(location, dict) else None,
            apply_url=first_str(data.get("absolute_url")) or external_job.final_url,
            external_job_id=str(data.get("id") or external_job.external_id),
            published_at=parse_datetime(data.get("first_published")),
            expires_at=parse_datetime(data.get("application_deadline")),
        )


class LeverConnector(UrlImportConnector):
    """jobs.lever.co/{site}/{id} → api.lever.co/v0/postings/{site}/{id} (EU: *.eu.lever.co)."""

    name = "lever"
    _HOSTS = {"jobs.lever.co": "api.lever.co", "jobs.eu.lever.co": "api.eu.lever.co"}
    _PATH = re.compile(rf"^/(?P<site>[A-Za-z0-9_.-]+)/(?P<id>{_UUID})(/apply)?/?$")

    def __init__(self, fetcher: SafeFetcher) -> None:
        self._fetcher = fetcher

    def _match(self, url: str) -> tuple[str, re.Match[str]] | None:
        parts = urlsplit(url)
        api_host = self._HOSTS.get(parts.hostname or "")
        match = self._PATH.match(parts.path) if api_host else None
        return (api_host, match) if api_host and match else None

    def can_handle_url(self, url: str) -> bool:
        return self._match(url) is not None

    async def fetch_job_by_url(self, url: str) -> ExternalJob:
        matched = self._match(url)
        if matched is None:
            raise UnsupportedSource("Not a Lever job URL")
        api_host, match = matched
        api = f"https://{api_host}/v0/postings/{match['site']}/{match['id']}"
        return ExternalJob(
            SourceType.LEVER, url, url, match["id"], await _get_json(self._fetcher, api)
        )

    async def normalize_job(self, external_job: ExternalJob) -> NormalizedJob:
        data = external_job.payload
        sections = [first_str(data.get("descriptionPlain")) or ""]
        for item in data.get("lists") or []:
            if isinstance(item, dict):
                heading = clean_text(item.get("text")) or ""
                body = html_to_text(item.get("content") or "")
                sections.append(f"{heading}\n{body}".strip())
        sections.append(first_str(data.get("additionalPlain")) or "")
        description = "\n\n".join(s for s in sections if s).strip()
        raw_categories = data.get("categories")
        categories: dict[str, Any] = raw_categories if isinstance(raw_categories, dict) else {}
        all_locations = [
            loc for loc in categories.get("allLocations") or [] if isinstance(loc, str)
        ]
        return NormalizedJob(
            source_type=SourceType.LEVER,
            source_url=external_job.source_url,
            final_url=external_job.final_url,
            title=_require(clean_text(data.get("text")), description),
            description=description,
            employer_name=None,  # the Lever API does not state the employer name
            location=" / ".join(all_locations) or clean_text(categories.get("location")),
            country=clean_text(data.get("country")),
            employment_type=clean_text(categories.get("commitment")),
            workplace_type=clean_text(data.get("workplaceType")),
            apply_url=first_str(data.get("applyUrl"), data.get("hostedUrl")),
            external_job_id=first_str(data.get("id")),
            published_at=parse_datetime(data.get("createdAt")),
        )


class AshbyConnector(UrlImportConnector):
    """jobs.ashbyhq.com/{org}/{id} → posting-api job board (board-level; filtered by id)."""

    name = "ashby"
    _PATH = re.compile(rf"^/(?P<org>[^/]+)/(?P<id>{_UUID})(/application)?/?$")

    def __init__(self, fetcher: SafeFetcher) -> None:
        self._fetcher = fetcher

    def _match(self, url: str) -> re.Match[str] | None:
        parts = urlsplit(url)
        return self._PATH.match(parts.path) if parts.hostname == "jobs.ashbyhq.com" else None

    def can_handle_url(self, url: str) -> bool:
        return self._match(url) is not None

    async def fetch_job_by_url(self, url: str) -> ExternalJob:
        match = self._match(url)
        if match is None:
            raise UnsupportedSource("Not an Ashby job URL")
        api = (
            f"https://api.ashbyhq.com/posting-api/job-board/{match['org']}?includeCompensation=true"
        )
        board = await _get_json(self._fetcher, api)
        jobs = board.get("jobs") if isinstance(board, dict) else None
        job = next(
            (
                j
                for j in jobs or []
                if isinstance(j, dict) and j.get("id", "").lower() == match["id"].lower()
            ),
            None,
        )
        if job is None or job.get("isListed") is False:
            raise FetchFailed("This Ashby job is no longer listed", retryable=False, status=404)
        return ExternalJob(SourceType.ASHBY, url, url, match["id"], job)

    async def normalize_job(self, external_job: ExternalJob) -> NormalizedJob:
        data = external_job.payload
        description = first_str(data.get("descriptionPlain")) or html_to_text(
            data.get("descriptionHtml") or ""
        )
        locations = [clean_text(data.get("location"))]
        for secondary in data.get("secondaryLocations") or []:
            if isinstance(secondary, dict):
                locations.append(clean_text(secondary.get("location")))
        unique = list(dict.fromkeys(loc for loc in locations if loc))
        address = (data.get("address") or {}).get("postalAddress") or {}
        workplace = clean_text(data.get("workplaceType"))
        if workplace is None and data.get("isRemote") is True:
            workplace = "Remote"
        return NormalizedJob(
            source_type=SourceType.ASHBY,
            source_url=external_job.source_url,
            final_url=external_job.final_url,
            title=_require(clean_text(data.get("title")), description),
            description=description,
            employer_name=None,  # the Ashby posting API does not state the employer name
            location=" / ".join(unique) or None,
            country=clean_text(address.get("addressCountry")),
            city=clean_text(address.get("addressLocality")),
            employment_type=clean_text(data.get("employmentType")),
            workplace_type=workplace,
            apply_url=first_str(data.get("applyUrl"), data.get("jobUrl")),
            external_job_id=first_str(data.get("id")),
            published_at=parse_datetime(data.get("publishedAt")),
        )
