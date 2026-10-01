import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResumeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    original_filename: str
    mime_type: str
    size_bytes: int
    text_hash: str
    text_chars: int = Field(description="Length of the extracted text")
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class ResumeRead(ResumeSummary):
    raw_text: str
