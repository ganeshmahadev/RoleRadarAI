import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.connectors.errors import SourceError
from app.connectors.http import validate_url
from app.models import SnapshotStatus, SourceType
from app.services.job_import import ImportOutcome


def _reference_url(value: str | None) -> str | None:
    """A link stored for reference (never fetched). Same safety rules as imports, incl. EURES."""
    if value is None or not value.strip():
        return None
    try:
        return validate_url(value).url
    except SourceError as exc:  # surface as a normal 422 validation error
        raise ValueError(exc.message) from exc


ReferenceUrl = Annotated[
    str | None, Field(default=None, max_length=2048), AfterValidator(_reference_url)
]


class JobImportUrlRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    company_id: uuid.UUID | None = None


class JobImportTextRequest(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=50, max_length=100_000)
    employer_name: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=300)
    source_url: ReferenceUrl = None
    apply_url: ReferenceUrl = None
    company_id: uuid.UUID | None = None


class CompanyRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    cvr: str


class JobSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: SourceType
    source_url: str
    final_url: str | None
    status: SnapshotStatus
    content_hash: str
    fetched_at: datetime
    normalized: dict[str, Any]


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    employer_name: str | None
    company: CompanyRef | None
    location: str | None
    source_type: SourceType
    source_url: str | None
    published_at: datetime | None
    created_at: datetime
    source_update_pending: bool


class JobRead(JobSummary):
    description: str
    country: str | None
    city: str | None
    employment_type: str | None
    workplace_type: str | None
    external_job_id: str | None
    apply_url: str | None
    expires_at: datetime | None
    content_hash: str
    updated_at: datetime
    sources: list[JobSourceRead]


class JobImportResponse(BaseModel):
    outcome: ImportOutcome
    job: JobRead
