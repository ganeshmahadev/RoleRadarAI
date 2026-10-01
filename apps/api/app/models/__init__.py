"""Import every ORM model here so Alembic autogenerate sees it."""

from app.models.company import Company, EuresStatus
from app.models.job import Job, JobSource, JobStatus, SnapshotStatus, SourceType
from app.models.match import MatchScore, MatchStatus
from app.models.match_run import MatchRun, MatchRunItem, RunItemStatus, RunScope, RunStatus
from app.models.resume import CandidateProfile, RemotePreference, Resume

__all__ = [
    "CandidateProfile",
    "Company",
    "EuresStatus",
    "Job",
    "JobSource",
    "JobStatus",
    "MatchScore",
    "MatchRun",
    "MatchRunItem",
    "MatchStatus",
    "RemotePreference",
    "Resume",
    "RunItemStatus",
    "RunScope",
    "RunStatus",
    "SnapshotStatus",
    "SourceType",
]
