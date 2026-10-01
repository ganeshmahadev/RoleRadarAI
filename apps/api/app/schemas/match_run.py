import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import RunItemStatus, RunScope, RunStatus


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: RunScope = RunScope.UNSCORED_OR_OUTDATED
    job_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    apply_relevance_filter: bool = True


class PlannedJobRead(BaseModel):
    job_id: uuid.UUID
    title: str
    matched_role: str | None


class RunPlanRead(BaseModel):
    scope: RunScope
    relevance_filter: bool
    target_roles: list[str]
    to_score: list[PlannedJobRead]
    not_relevant: list[PlannedJobRead]
    seconds_per_job: float | None


class RunItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    job_title: str
    status: RunItemStatus
    reason: str | None
    error_code: str | None
    matched_role: str | None
    match_id: uuid.UUID | None
    completed_at: datetime | None


class RunRead(BaseModel):
    id: uuid.UUID
    status: RunStatus
    scope: RunScope
    relevance_filter: bool
    target_roles: list[str]
    counts: dict[str, int]
    finished: int
    total: int
    current_job_id: uuid.UUID | None
    current_job_title: str | None
    seconds_per_job: float | None
    seconds_remaining: float | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    items: list[RunItemRead]
