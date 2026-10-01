import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    false,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.db.base import Base
from app.db.types import str_enum
from app.models.company import Company


class SourceType(StrEnum):
    JSONLD = "jsonld"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    GENERIC_HTML = "generic_html"
    MANUAL = "manual"


class SnapshotStatus(StrEnum):
    """Review state of a fetched source snapshot (PRD §15: never silently overwrite)."""

    ACCEPTED = "ACCEPTED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"


class Job(Base):
    """One canonical vacancy; may be referenced by several sources (PRD §15, §27)."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )

    title: Mapped[str] = mapped_column(Text)
    normalized_title: Mapped[str] = mapped_column(Text)
    # Employer as stated by the source; needed when the job is not linked to a company.
    employer_name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)  # plain text, never stored as HTML

    location: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    employment_type: Mapped[str | None] = mapped_column(Text)
    workplace_type: Mapped[str | None] = mapped_column(Text)

    source_type: Mapped[SourceType] = mapped_column(str_enum(SourceType, "source_type"))
    source_url: Mapped[str | None] = mapped_column(Text)
    external_job_id: Mapped[str | None] = mapped_column(Text)
    apply_url: Mapped[str | None] = mapped_column(Text)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    content_hash: Mapped[str] = mapped_column(Text, index=True)
    dedup_key: Mapped[str] = mapped_column(Text, unique=True)
    source_update_pending: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company | None] = relationship(lazy="selectin")
    sources: Mapped[list["JobSource"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobSource.fetched_at",
    )


class JobSource(Base):
    """A fetched snapshot of a job from one source URL."""

    __tablename__ = "job_sources"
    __table_args__ = (
        UniqueConstraint(
            "source_url", "content_hash", name="uq_job_sources_source_url_content_hash"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[SourceType] = mapped_column(str_enum(SourceType, "source_type"))
    source_url: Mapped[str] = mapped_column(Text, index=True)  # as submitted
    final_url: Mapped[str | None] = mapped_column(Text)  # after validated redirects
    external_job_id: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[SnapshotStatus] = mapped_column(
        str_enum(SnapshotStatus, "snapshot_status"), default=SnapshotStatus.ACCEPTED
    )
    normalized: Mapped[dict[str, Any]] = mapped_column(JSONB)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job] = relationship(back_populates="sources")


# Number of canonical jobs linked to a company ("Jobs found", PRD §23).
Company.jobs_count = column_property(  # type: ignore[assignment]
    select(func.count(Job.id))
    .where(Job.company_id == Company.id)
    .correlate_except(Job)
    .scalar_subquery()
)
