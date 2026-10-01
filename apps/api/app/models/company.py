import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Integer, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EuresStatus(StrEnum):
    """EURES discovery workflow state (PRD §8)."""

    NOT_CHECKED = "NOT_CHECKED"
    OPENED = "OPENED"
    CHECKED_NO_JOBS = "CHECKED_NO_JOBS"
    JOB_FOUND = "JOB_FOUND"
    ERROR = "ERROR"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    company_name: Mapped[str] = mapped_column(Text)
    normalized_name: Mapped[str] = mapped_column(Text, index=True)
    # CVR is text and preserved exactly as published; never cast to an integer.
    cvr: Mapped[str] = mapped_column(Text, unique=True)
    # Position in the SIRI source list; defines queue order ("next unchecked").
    source_position: Mapped[int | None] = mapped_column(Integer, index=True)

    siri_certified: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    siri_source_url: Mapped[str | None] = mapped_column(Text)
    siri_last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    eures_search_url: Mapped[str] = mapped_column(Text)
    eures_status: Mapped[EuresStatus] = mapped_column(
        Enum(
            EuresStatus,
            name="eures_status",
            native_enum=False,
            create_constraint=True,
            length=32,
            validate_strings=True,
        ),
        default=EuresStatus.NOT_CHECKED,
        server_default=EuresStatus.NOT_CHECKED.value,
        index=True,
    )
    eures_last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    eures_notes: Mapped[str | None] = mapped_column(Text)

    website_url: Mapped[str | None] = mapped_column(Text)
    careers_url: Mapped[str | None] = mapped_column(Text)
    ats_provider: Mapped[str | None] = mapped_column(Text)

    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    if TYPE_CHECKING:
        # column_property defined in app/models/job.py (needs the Job table)
        jobs_count: int
