import uuid

from pydantic import BaseModel, Field

from app.models import EuresStatus


class EuresSearch(BaseModel):
    company_id: uuid.UUID
    company_name: str
    url: str
    status: EuresStatus


class EuresQueueStats(BaseModel):
    total: int
    checked: int
    remaining: int
    by_status: dict[EuresStatus, int]


class CompanyUpdate(BaseModel):
    """User-editable company fields. Only EURES notes in P3."""

    eures_notes: str | None = Field(default=None, max_length=5000)
