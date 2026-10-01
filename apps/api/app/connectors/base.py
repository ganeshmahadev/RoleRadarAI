"""Job-source connector contract (PRD §9).

Every vacancy source implements JobSourceConnector. Business services only see
ExternalJob / NormalizedJob, never source-specific parsing.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from app.connectors.errors import UnsupportedOperation
from app.models import Company, SourceType


@dataclass(frozen=True)
class ExternalJob:
    """A vacancy as retrieved from a source, before normalization."""

    source_type: SourceType
    source_url: str  # as submitted
    final_url: str  # after validated redirects
    external_id: str | None
    payload: dict[str, Any]  # raw source data (API JSON or extracted JSON-LD/HTML fields)


@dataclass(frozen=True)
class NormalizedJob:
    source_type: SourceType
    source_url: str
    final_url: str
    title: str
    description: str  # plain text
    employer_name: str | None = None
    location: str | None = None
    country: str | None = None
    city: str | None = None
    employment_type: str | None = None
    workplace_type: str | None = None
    apply_url: str | None = None
    external_job_id: str | None = None
    published_at: datetime | None = None
    expires_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> dict[str, Any]:
        """JSON-serializable form stored on JobSource.normalized."""
        data = asdict(self)
        for key in ("published_at", "expires_at"):
            value = data[key]
            data[key] = value.isoformat() if value else None
        data["source_type"] = self.source_type.value
        return data


@runtime_checkable
class JobSourceConnector(Protocol):
    name: str

    def can_handle_url(self, url: str) -> bool: ...

    async def fetch_job_by_url(self, url: str) -> ExternalJob: ...

    async def search_company(self, company: Company) -> list[ExternalJob]: ...

    async def fetch_job(self, external_id: str) -> ExternalJob: ...

    async def normalize_job(self, external_job: ExternalJob) -> NormalizedJob: ...


class UrlImportConnector:
    """Base for connectors that import one vacancy from a URL (no company search)."""

    name = "url_import"

    def can_handle_url(self, url: str) -> bool:
        raise NotImplementedError

    async def fetch_job_by_url(self, url: str) -> ExternalJob:
        raise NotImplementedError

    async def normalize_job(self, external_job: ExternalJob) -> NormalizedJob:
        raise NotImplementedError

    async def search_company(self, company: Company) -> list[ExternalJob]:
        raise UnsupportedOperation(f"{self.name} cannot search by company")

    async def fetch_job(self, external_id: str) -> ExternalJob:
        raise UnsupportedOperation(f"{self.name} needs a job URL, not a bare id")
