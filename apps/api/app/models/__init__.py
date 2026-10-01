"""Import every ORM model here so Alembic autogenerate sees it."""

from app.models.company import Company, EuresStatus
from app.models.job import Job, JobSource, SnapshotStatus, SourceType

__all__ = ["Company", "EuresStatus", "Job", "JobSource", "SnapshotStatus", "SourceType"]
