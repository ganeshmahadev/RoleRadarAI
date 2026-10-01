import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import str_enum
from app.models.match_run import RunStatus


class DiscoveryTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class DiscoveryPhase(StrEnum):
    QUEUED = "QUEUED"
    SCRAPING = "SCRAPING"  # job boards via JobSpy
    EURES = "EURES"  # EURES scan (PRD §84)
    SCORING = "SCORING"
    FINISHED = "FINISHED"


DEFAULT_SITES = ["indeed", "linkedin", "google"]


class DiscoverySettings(Base):
    """Single-row search settings for automated discovery (PRD §84). Row id is always 1."""

    __tablename__ = "discovery_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Empty = use the primary resume's profile target roles.
    search_terms: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    location: Mapped[str] = mapped_column(Text, default="Denmark", server_default="Denmark")
    sites: Mapped[list[str]] = mapped_column(
        JSONB,
        default=lambda: list(DEFAULT_SITES),
        server_default='["indeed", "linkedin", "google"]',
    )
    results_per_site: Mapped[int] = mapped_column(Integer, default=25, server_default="25")
    hours_old: Mapped[int] = mapped_column(Integer, default=72, server_default="72")
    eures_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    eures_companies_per_run: Mapped[int] = mapped_column(Integer, default=120, server_default="120")
    scrape_budget_minutes: Mapped[int] = mapped_column(Integer, default=20, server_default="20")
    total_budget_minutes: Mapped[int] = mapped_column(Integer, default=60, server_default="60")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DiscoveryRun(Base):
    """One "Search now" or daily discovery run: scrape → import → score (PRD §84)."""

    __tablename__ = "discovery_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trigger: Mapped[DiscoveryTrigger] = mapped_column(
        str_enum(DiscoveryTrigger, "discovery_trigger")
    )
    status: Mapped[RunStatus] = mapped_column(
        str_enum(RunStatus, "discovery_status"), default=RunStatus.QUEUED, index=True
    )
    phase: Mapped[DiscoveryPhase] = mapped_column(
        str_enum(DiscoveryPhase, "discovery_phase"), default=DiscoveryPhase.QUEUED
    )
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB)  # snapshot used for this run
    # One entry per searched source: {source, term, status, found, created, attached, unchanged,
    # skipped, linked_siri, message}
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")
    new_jobs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")
    match_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("match_runs.id", ondelete="SET NULL")
    )
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scrape_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
