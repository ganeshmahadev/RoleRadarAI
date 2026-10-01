import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.models import RemotePreference

Item = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
CefrLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2", "Native"]


def _clean_items(values: list[str]) -> list[str]:
    """Drop blanks and case-insensitive duplicates, keeping the user's order."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


TagList = Annotated[list[Item], Field(max_length=50), AfterValidator(_clean_items)]


class LanguageEntry(BaseModel):
    language: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    level: CefrLevel


def _unique_languages(values: list[LanguageEntry]) -> list[LanguageEntry]:
    seen: set[str] = set()
    out: list[LanguageEntry] = []
    for entry in values:
        if entry.language.casefold() not in seen:
            seen.add(entry.language.casefold())
            out.append(entry)
    return out


LanguageList = Annotated[
    list[LanguageEntry], Field(max_length=20), AfterValidator(_unique_languages)
]
Years = Annotated[Decimal, Field(ge=0, le=60, decimal_places=1)]


class CandidateProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resume_id: uuid.UUID
    target_roles: list[str]
    skills: list[str]
    years_experience: Decimal | None
    industries: list[str]
    education: list[str]
    certifications: list[str]
    languages: list[LanguageEntry]
    preferred_locations: list[str]
    remote_preference: RemotePreference | None
    work_authorization: list[str]
    updated_at: datetime


class CandidateProfileUpdate(BaseModel):
    """Partial update: only fields present in the request change. `null` clears scalars."""

    model_config = ConfigDict(extra="forbid")

    target_roles: TagList | None = None
    skills: TagList | None = None
    years_experience: Years | None = None
    industries: TagList | None = None
    education: TagList | None = None
    certifications: TagList | None = None
    languages: LanguageList | None = None
    preferred_locations: TagList | None = None
    remote_preference: RemotePreference | None = None
    work_authorization: TagList | None = None
