import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.models import DiscoveryPhase, DiscoveryTrigger, RunStatus
from app.schemas.match_run import RunRead
from app.schemas.profile import _clean_items

Site = Literal["indeed", "linkedin", "google"]
Term = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class DiscoverySettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    search_terms: list[str]
    location: str
    sites: list[str]
    results_per_site: int
    hours_old: int
    eures_enabled: bool
    eures_companies_per_run: int
    scrape_budget_minutes: int
    total_budget_minutes: int
    # Not stored: derived from the environment and the profile.
    effective_terms: list[str] = Field(default_factory=list)
    jobspy_enabled: bool = False
    eures_scraper_enabled: bool = False
    eures_available: bool = False


class DiscoverySettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search_terms: (
        Annotated[list[Term], Field(max_length=20), AfterValidator(_clean_items)] | None
    ) = None
    location: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
        | None
    ) = None
    sites: Annotated[list[Site], Field(max_length=3)] | None = None
    results_per_site: Annotated[int, Field(ge=1, le=100)] | None = None
    hours_old: Annotated[int, Field(ge=1, le=720)] | None = None
    eures_enabled: bool | None = None
    eures_companies_per_run: Annotated[int, Field(ge=1, le=982)] | None = None
    scrape_budget_minutes: Annotated[int, Field(ge=1, le=240)] | None = None
    total_budget_minutes: Annotated[int, Field(ge=1, le=600)] | None = None


class DiscoveryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger: DiscoveryTrigger = DiscoveryTrigger.MANUAL


class DiscoveryRunRead(BaseModel):
    id: uuid.UUID
    trigger: DiscoveryTrigger
    status: RunStatus
    phase: DiscoveryPhase
    settings: dict[str, Any]
    sources: list[dict[str, Any]]
    new_jobs: list[dict[str, Any]]
    scoring: RunRead | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    scrape_deadline: datetime | None
    deadline: datetime | None
    completed_at: datetime | None
