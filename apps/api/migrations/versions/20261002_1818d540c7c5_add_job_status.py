"""add job status

Revision ID: 1818d540c7c5
Revises: f8b28895d5f0
Create Date: 2026-10-02 01:46:07.134195
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1818d540c7c5"
down_revision: str | None = "f8b28895d5f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "status",
            sa.Enum(
                "NEW",
                "SAVED",
                "IGNORED",
                name="job_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            server_default="NEW",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_jobs_job_status"), "jobs", "status IN ('NEW', 'SAVED', 'IGNORED')"
    )
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_constraint(op.f("ck_jobs_job_status"), "jobs", type_="check")
    op.drop_column("jobs", "status")
