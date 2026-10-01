"""Job-board search through JobSpy (github.com/speedyapply/JobSpy, MIT) — PRD §84.

User override for local educational/testing use. Guardrails: sequential, small result caps,
no proxies, no user-agent tricks; HTTP 403/429 or a captcha marks the board as blocked for the
run instead of retrying around it.
"""

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

from app.connectors.base import NormalizedJob
from app.connectors.text import clean_text, html_to_text
from app.models import SourceType

SITES = {"indeed": SourceType.INDEED, "linkedin": SourceType.LINKEDIN, "google": SourceType.GOOGLE}
MIN_DESCRIPTION_CHARS = 80
_BLOCK_MARKERS = ("429", "403", "too many requests", "captcha", "blocked", "forbidden")


class JobSpyClient(Protocol):
    def scrape(self, params: dict[str, Any]) -> list[dict[str, Any]]: ...


class LiveJobSpyClient:
    """Calls the real library (blocking; run it in a thread)."""

    def scrape(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        from jobspy import scrape_jobs  # heavy import (pandas); only when actually used

        frame = scrape_jobs(**params)
        records: list[dict[str, Any]] = frame.to_dict("records")
        return [{k: _clean_value(v) for k, v in row.items()} for row in records]


def _clean_value(value: Any) -> Any:
    """pandas uses NaN/NaT for missing values; normalize to None."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if type(value).__name__ in ("NaTType", "NAType"):
        return None
    return value


@dataclass(frozen=True)
class SearchSpec:
    site: str
    term: str
    location: str
    results: int
    hours_old: int


def build_params(spec: SearchSpec) -> dict[str, Any]:
    params: dict[str, Any] = {
        "site_name": [spec.site],
        "search_term": spec.term,
        "location": spec.location,
        "results_wanted": spec.results,
        "hours_old": spec.hours_old,
        "description_format": "html",
        "verbose": 0,
    }
    if spec.site == "indeed":
        params["country_indeed"] = "denmark"  # SIRI companies are Danish
    elif spec.site == "linkedin":
        params["fetch_description"] = True  # one extra request per job; keep results small
    elif spec.site == "google":
        recency = " since yesterday" if spec.hours_old <= 24 else ""
        params["google_search_term"] = f"{spec.term} jobs in {spec.location}{recency}"
    return params


def is_blocked(error: Exception) -> bool:
    text = f"{type(error).__name__} {error}".lower()
    return any(marker in text for marker in _BLOCK_MARKERS)


def _published(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        try:
            return _published(date.fromisoformat(value.strip()[:10]))
        except ValueError:
            return None
    return None


def row_to_job(row: dict[str, Any], site: str) -> NormalizedJob | None:
    """Map one JobSpy row; None when it lacks a URL, title or a usable description."""
    url = clean_text(row.get("job_url"))
    title = clean_text(row.get("title"))
    raw = row.get("description")
    description = html_to_text(raw) if isinstance(raw, str) else ""
    if not url or not title or len(description) < MIN_DESCRIPTION_CHARS:
        return None
    if not url.startswith(("https://", "http://")):
        return None
    direct = clean_text(row.get("job_url_direct"))
    job_type = row.get("job_type")
    if isinstance(job_type, list):
        job_type = ", ".join(str(t) for t in job_type)
    return NormalizedJob(
        source_type=SITES[site],
        source_url=url,
        final_url=url,
        title=title,
        description=description,
        employer_name=clean_text(row.get("company")),
        location=clean_text(row.get("location")),
        employment_type=clean_text(job_type),
        workplace_type="remote" if row.get("is_remote") is True else None,
        apply_url=direct if direct and direct.startswith(("https://", "http://")) else url,
        external_job_id=clean_text(str(row["id"])) if row.get("id") is not None else None,
        published_at=_published(row.get("date_posted")),
    )


def json_safe(row: dict[str, Any]) -> dict[str, Any]:
    """Raw payload stored on JobSource (JSONB): dates and other objects become strings."""
    safe: dict[str, Any] = {}
    for key, value in row.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            safe[key] = value
        elif isinstance(value, (list, tuple)):
            safe[key] = [v if isinstance(v, (str, int, float, bool)) else str(v) for v in value]
        else:
            safe[key] = str(value)
    return safe
