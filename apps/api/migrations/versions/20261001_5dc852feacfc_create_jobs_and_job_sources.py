"""create jobs and job sources

Revision ID: 5dc852feacfc
Revises: 885ccfb342f6
Create Date: 2026-10-01 09:10:41.014543
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5dc852feacfc"
down_revision: str | None = "885ccfb342f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("normalized_title", sa.Text(), nullable=False),
        sa.Column("employer_name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("employment_type", sa.Text(), nullable=True),
        sa.Column("workplace_type", sa.Text(), nullable=True),
        sa.Column(
            "source_type",
            sa.Enum(
                "jsonld",
                "greenhouse",
                "lever",
                "ashby",
                "generic_html",
                "manual",
                name="source_type",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("external_job_id", sa.Text(), nullable=True),
        sa.Column("apply_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("dedup_key", sa.Text(), nullable=False),
        sa.Column(
            "source_update_pending", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('jsonld', 'greenhouse', 'lever', 'ashby', 'generic_html', 'manual')",
            name=op.f("ck_jobs_source_type"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_jobs_company_id_companies"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("dedup_key", name=op.f("uq_jobs_dedup_key")),
    )
    op.create_index(op.f("ix_jobs_company_id"), "jobs", ["company_id"], unique=False)
    op.create_index(op.f("ix_jobs_content_hash"), "jobs", ["content_hash"], unique=False)
    op.create_table(
        "job_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum(
                "jsonld",
                "greenhouse",
                "lever",
                "ashby",
                "generic_html",
                "manual",
                name="source_type",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("external_job_id", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ACCEPTED",
                "PENDING",
                "REJECTED",
                name="snapshot_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("normalized", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('jsonld', 'greenhouse', 'lever', 'ashby', 'generic_html', 'manual')",
            name=op.f("ck_job_sources_source_type"),
        ),
        sa.CheckConstraint(
            "status IN ('ACCEPTED', 'PENDING', 'REJECTED')",
            name=op.f("ck_job_sources_snapshot_status"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_job_sources_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_sources")),
        sa.UniqueConstraint(
            "source_url", "content_hash", name="uq_job_sources_source_url_content_hash"
        ),
    )
    op.create_index(op.f("ix_job_sources_job_id"), "job_sources", ["job_id"], unique=False)
    op.create_index(op.f("ix_job_sources_source_url"), "job_sources", ["source_url"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_sources_source_url"), table_name="job_sources")
    op.drop_index(op.f("ix_job_sources_job_id"), table_name="job_sources")
    op.drop_table("job_sources")
    op.drop_index(op.f("ix_jobs_content_hash"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_company_id"), table_name="jobs")
    op.drop_table("jobs")
