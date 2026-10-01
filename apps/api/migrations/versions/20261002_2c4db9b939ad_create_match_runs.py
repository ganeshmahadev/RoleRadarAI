"""create match runs

Revision ID: 2c4db9b939ad
Revises: 1818d540c7c5
Create Date: 2026-10-02 02:05:51.455479
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2c4db9b939ad"
down_revision: str | None = "1818d540c7c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "match_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resume_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "RUNNING",
                "DONE",
                "CANCELLED",
                "FAILED",
                name="run_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "scope",
            sa.Enum(
                "unscored",
                "unscored_or_outdated",
                "jobs",
                name="run_scope",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("relevance_filter", sa.Boolean(), nullable=False),
        sa.Column(
            "target_roles",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("current_job_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "scope IN ('unscored', 'unscored_or_outdated', 'jobs')",
            name=op.f("ck_match_runs_run_scope"),
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'DONE', 'CANCELLED', 'FAILED')",
            name=op.f("ck_match_runs_run_status"),
        ),
        sa.ForeignKeyConstraint(
            ["current_job_id"],
            ["jobs.id"],
            name=op.f("fk_match_runs_current_job_id_jobs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resumes.id"],
            name=op.f("fk_match_runs_resume_id_resumes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_match_runs")),
    )
    op.create_index(op.f("ix_match_runs_resume_id"), "match_runs", ["resume_id"], unique=False)
    op.create_index(op.f("ix_match_runs_status"), "match_runs", ["status"], unique=False)
    op.create_table(
        "match_run_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("job_title", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "DONE",
                "CACHED",
                "SKIPPED",
                "FAILED",
                name="run_item_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("matched_role", sa.Text(), nullable=True),
        sa.Column("match_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'DONE', 'CACHED', 'SKIPPED', 'FAILED')",
            name=op.f("ck_match_run_items_run_item_status"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_match_run_items_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["match_scores.id"],
            name=op.f("fk_match_run_items_match_id_match_scores"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["match_runs.id"],
            name=op.f("fk_match_run_items_run_id_match_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_match_run_items")),
        sa.UniqueConstraint("run_id", "job_id", name="uq_match_run_items_run_job"),
    )


def downgrade() -> None:
    op.drop_table("match_run_items")
    op.drop_index(op.f("ix_match_runs_status"), table_name="match_runs")
    op.drop_index(op.f("ix_match_runs_resume_id"), table_name="match_runs")
    op.drop_table("match_runs")
