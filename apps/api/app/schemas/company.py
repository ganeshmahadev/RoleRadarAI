import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models import EuresStatus

CompanySort = Literal["position", "name", "last_checked"]


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    normalized_name: str
    cvr: str
    source_position: int | None
    siri_certified: bool
    siri_source_url: str | None
    siri_last_seen_at: datetime | None
    eures_search_url: str
    eures_status: EuresStatus
    eures_last_checked_at: datetime | None
    eures_notes: str | None
    website_url: str | None
    careers_url: str | None
    ats_provider: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
