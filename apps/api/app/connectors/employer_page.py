"""Employer career pages: JSON-LD JobPosting first, generic HTML fallback (PRD §26).

Subject to the robots.txt policy; a disallow means "use manual JD paste".
"""

from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from app.connectors.base import ExternalJob, NormalizedJob, UrlImportConnector
from app.connectors.errors import ExtractionFailed, UnsupportedSource
from app.connectors.http import SafeFetcher
from app.connectors.jsonld import extract_fields, find_job_postings
from app.connectors.robots import RobotsPolicy
from app.connectors.text import clean_text, html_to_text
from app.models import SourceType

# Below these lengths the extraction is treated as failed rather than importing a stub.
MIN_JSONLD_DESCRIPTION_CHARS = 50
MIN_GENERIC_DESCRIPTION_CHARS = 200


class EmployerPageConnector(UrlImportConnector):
    name = "employer_page"

    def __init__(self, fetcher: SafeFetcher, robots: RobotsPolicy) -> None:
        self._fetcher = fetcher
        self._robots = robots

    def can_handle_url(self, url: str) -> bool:
        return True  # catch-all; the registry lists it last

    async def fetch_job_by_url(self, url: str) -> ExternalJob:
        await self._robots.ensure_allowed(url)
        response = await self._fetcher.get(url, accept="text/html,application/xhtml+xml")
        if urlsplit(response.url).netloc != urlsplit(url).netloc:
            await self._robots.ensure_allowed(response.url)
        content_type = response.content_type.lower()
        if content_type and "html" not in content_type:
            raise UnsupportedSource(f"Expected an HTML job page, got {content_type.split(';')[0]}")
        html = response.text()
        postings = find_job_postings(html)
        if postings:
            return ExternalJob(
                source_type=SourceType.JSONLD,
                source_url=url,
                final_url=response.url,
                external_id=None,
                payload={"jsonld": postings[0]},
            )
        return self._generic(url, response.url, html)

    def _generic(self, url: str, final_url: str, html: str) -> ExternalJob:
        """Generic permitted HTML extraction (PRD §26 priority 4)."""
        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.find("h1")
        title = clean_text(h1.get_text(" ")) if isinstance(h1, Tag) else None
        title = title or _meta(soup, "og:title")
        if not title and soup.title is not None:
            title = clean_text(soup.title.get_text())
        container = next(
            (
                found
                for selector in ("main", "article", "[role=main]", "#content", "body")
                if isinstance(found := soup.select_one(selector), Tag)
            ),
            None,
        )
        if container is not None:
            for noise in container.select("nav, header, footer, aside"):
                noise.decompose()
        description = html_to_text(str(container)) if container is not None else ""
        if not title or len(description) < MIN_GENERIC_DESCRIPTION_CHARS:
            raise ExtractionFailed(
                "Could not find a job description on this page. Paste it manually instead."
            )
        return ExternalJob(
            source_type=SourceType.GENERIC_HTML,
            source_url=url,
            final_url=final_url,
            external_id=None,
            payload={
                "generic": {
                    "title": title,
                    "description": description,
                    "site_name": _meta(soup, "og:site_name"),
                }
            },
        )

    async def normalize_job(self, external_job: ExternalJob) -> NormalizedJob:
        payload: dict[str, Any] = external_job.payload
        if external_job.source_type is SourceType.JSONLD:
            fields = extract_fields(payload["jsonld"])
            if not fields.title or len(fields.description) < MIN_JSONLD_DESCRIPTION_CHARS:
                raise ExtractionFailed(
                    "The job posting data on this page is incomplete. "
                    "Paste the job description manually."
                )
            return NormalizedJob(
                source_type=SourceType.JSONLD,
                source_url=external_job.source_url,
                final_url=external_job.final_url,
                title=fields.title,
                description=fields.description,
                employer_name=fields.employer_name,
                location=fields.location,
                country=fields.country,
                city=fields.city,
                employment_type=fields.employment_type,
                workplace_type=fields.workplace_type,
                apply_url=fields.apply_url or external_job.final_url,
                external_job_id=fields.external_id,
                published_at=fields.published_at,
                expires_at=fields.expires_at,
            )
        if external_job.source_type is SourceType.GENERIC_HTML:
            generic = payload["generic"]
            return NormalizedJob(
                source_type=SourceType.GENERIC_HTML,
                source_url=external_job.source_url,
                final_url=external_job.final_url,
                title=generic["title"],
                description=generic["description"],
                employer_name=generic.get("site_name"),
                apply_url=external_job.final_url,
            )
        raise UnsupportedSource(f"Unexpected payload for {external_job.source_type}")


def _meta(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop})
    return clean_text(tag.get("content")) if isinstance(tag, Tag) else None
