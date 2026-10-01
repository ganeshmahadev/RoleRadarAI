import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import str_enum


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class RunScope(StrEnum):
    UNSCORED = "unscored"
    UNSCORED_OR_OUTDATED = "unscored_or_outdated"
    JOBS = "jobs"


class RunItemStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"  # scored now
    CACHED = "CACHED"  # an identical score already existed
    SKIPPED = "SKIPPED"  # not relevant, cancelled, or the run stopped
    FAILED = "FAILED"


class MatchRun(Base):
    """A batch scoring of several jobs against the primary resume (PRD §43–§44, §57)."""

    __tablename__ = "match_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[RunStatus] = mapped_column(
        str_enum(RunStatus, "run_status"), default=RunStatus.QUEUED, index=True
    )
    scope: Mapped[RunScope] = mapped_column(str_enum(RunScope, "run_scope"))
    relevance_filter: Mapped[bool] = mapped_column(Boolean)
    target_roles: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL")
    )
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["MatchRunItem"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="MatchRunItem.position",
        lazy="selectin",
    )


class MatchRunItem(Base):
    __tablename__ = "match_run_items"
    __table_args__ = (UniqueConstraint("run_id", "job_id", name="uq_match_run_items_run_job"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("match_runs.id", ondelete="CASCADE"))
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    job_title: Mapped[str] = mapped_column(Text)  # snapshot for progress display
    status: Mapped[RunItemStatus] = mapped_column(
        str_enum(RunItemStatus, "run_item_status"), default=RunItemStatus.PENDING
    )
    reason: Mapped[str | None] = mapped_column(Text)  # why skipped / failed
    error_code: Mapped[str | None] = mapped_column(Text)
    matched_role: Mapped[str | None] = mapped_column(Text)  # target role that made it relevant
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("match_scores.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped[MatchRun] = relationship(back_populates="items")
