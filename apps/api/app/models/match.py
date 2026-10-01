import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, Text, false, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import str_enum


class MatchStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class MatchScore(Base):
    """One scoring of one job against one resume under one model revision and rubric (PRD §16).

    Stores every dimension and the evidence, never only a single number.
    """

    __tablename__ = "match_scores"
    __table_args__ = (
        # Cache: at most one queued/running/done match per input (failed ones may repeat).
        Index(
            "uq_match_scores_live_input",
            "input_hash",
            unique=True,
            postgresql_where=text("status <> 'FAILED'"),
        ),
        Index("ix_match_scores_job_resume_created", "job_id", "resume_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[MatchStatus] = mapped_column(
        str_enum(MatchStatus, "match_status"), default=MatchStatus.QUEUED
    )

    # Reproducibility / cache key inputs (PRD §16, §29).
    input_hash: Mapped[str] = mapped_column(Text)
    resume_text_hash: Mapped[str] = mapped_column(Text)
    profile_hash: Mapped[str] = mapped_column(Text)
    job_content_hash: Mapped[str] = mapped_column(Text)
    model_provider: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(Text)
    model_revision: Mapped[str] = mapped_column(Text)
    rubric_version: Mapped[str] = mapped_column(Text)

    # Dimension scores, 0..100 (decision 2026-10-02). must_have is NULL when nothing is stated.
    must_have_fit: Mapped[float | None] = mapped_column(Float)
    skills_fit: Mapped[float | None] = mapped_column(Float)
    experience_fit: Mapped[float | None] = mapped_column(Float)
    role_fit: Mapped[float | None] = mapped_column(Float)
    seniority_fit: Mapped[float | None] = mapped_column(Float)
    domain_fit: Mapped[float | None] = mapped_column(Float)
    education_fit: Mapped[float | None] = mapped_column(Float)

    hard_blocker: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    requirements: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    matched_requirements: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    missing_requirements: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    uncertain_requirements: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    overall_score: Mapped[float | None] = mapped_column(Float)
    category: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")

    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
