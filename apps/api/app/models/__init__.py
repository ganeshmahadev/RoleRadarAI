"""Import every ORM model here so Alembic autogenerate sees it."""

from app.models.company import Company, EuresStatus
from app.models.job import Job, JobSource, SnapshotStatus, SourceType
from app.models.resume import CandidateProfile, RemotePreference, Resume

__all__ = [
    "CandidateProfile",
    "Company",
    "EuresStatus",
    "Job",
    "JobSource",
    "RemotePreference",
    "Resume",
    "SnapshotStatus",
    "SourceType",
]
