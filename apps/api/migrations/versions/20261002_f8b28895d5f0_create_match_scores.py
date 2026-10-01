"""create match scores

Revision ID: f8b28895d5f0
Revises: 886b77401096
Create Date: 2026-10-02 00:40:47.414954
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8b28895d5f0"
down_revision: str | None = "886b77401096"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "match_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("resume_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "RUNNING",
                "DONE",
                "FAILED",
                name="match_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("resume_text_hash", sa.Text(), nullable=False),
        sa.Column("profile_hash", sa.Text(), nullable=False),
        sa.Column("job_content_hash", sa.Text(), nullable=False),
        sa.Column("model_provider", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("model_revision", sa.Text(), nullable=False),
        sa.Column("rubric_version", sa.Text(), nullable=False),
        sa.Column("must_have_fit", sa.Float(), nullable=True),
        sa.Column("skills_fit", sa.Float(), nullable=True),
        sa.Column("experience_fit", sa.Float(), nullable=True),
        sa.Column("role_fit", sa.Float(), nullable=True),
        sa.Column("seniority_fit", sa.Float(), nullable=True),
        sa.Column("domain_fit", sa.Float(), nullable=True),
        sa.Column("education_fit", sa.Float(), nullable=True),
        sa.Column("hard_blocker", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "matched_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "missing_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "uncertain_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column(
            "explanation",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED')",
            name=op.f("ck_match_scores_match_status"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_match_scores_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resumes.id"],
            name=op.f("fk_match_scores_resume_id_resumes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_match_scores")),
    )
    op.create_index(
        "ix_match_scores_job_resume_created",
        "match_scores",
        ["job_id", "resume_id", "created_at"],
        unique=False,
    )
    op.create_index(op.f("ix_match_scores_resume_id"), "match_scores", ["resume_id"], unique=False)
    op.create_index(
        "uq_match_scores_live_input",
        "match_scores",
        ["input_hash"],
        unique=True,
        postgresql_where=sa.text("status <> 'FAILED'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_match_scores_live_input",
        table_name="match_scores",
        postgresql_where=sa.text("status <> 'FAILED'"),
    )
    op.drop_index(op.f("ix_match_scores_resume_id"), table_name="match_scores")
    op.drop_index("ix_match_scores_job_resume_created", table_name="match_scores")
    op.drop_table("match_scores")
