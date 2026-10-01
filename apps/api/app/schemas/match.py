import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import MatchStatus


class ScoreRequest(BaseModel):
    resume_id: uuid.UUID | None = Field(default=None, description="Defaults to the primary resume")


class RequirementCheck(BaseModel):
    key: str
    label: str
    status: str  # MET | PARTIAL | NOT_MET | UNKNOWN
    classification: str  # blocker | warning | informational | none
    stated_probability: float
    met_probability: float | None


class Dimensions(BaseModel):
    """0–100 each. must_have is null when the vacancy states no hard requirement."""

    must_have: float | None
    skills: float | None
    experience: float | None
    role: float | None
    seniority: float | None
    domain: float | None
    education: float | None


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    resume_id: uuid.UUID
    status: MatchStatus
    overall_score: float | None
    category: str | None
    hard_blocker: bool
    dimensions: Dimensions
    requirements: list[RequirementCheck]
    matched_requirements: list[str]
    uncertain_requirements: list[str]
    missing_requirements: list[str]
    explanation: dict[str, Any]
    model_provider: str
    model_name: str
    model_revision: str
    rubric_version: str
    input_hash: str
    error_code: str | None
    error_message: str | None
    attempts: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    outdated: bool = Field(
        default=False, description="Resume, profile, job text or rubric changed since scoring"
    )


class ScoreResponse(BaseModel):
    match: MatchRead
    cached: bool = Field(description="True when an identical input was already scored")
