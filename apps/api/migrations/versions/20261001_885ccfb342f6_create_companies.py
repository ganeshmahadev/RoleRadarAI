"""create companies

Revision ID: 885ccfb342f6
Revises:
Create Date: 2026-10-01 02:36:25.429564
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "885ccfb342f6"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("cvr", sa.Text(), nullable=False),
        sa.Column("source_position", sa.Integer(), nullable=True),
        sa.Column("siri_certified", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("siri_source_url", sa.Text(), nullable=True),
        sa.Column("siri_last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eures_search_url", sa.Text(), nullable=False),
        sa.Column(
            "eures_status",
            sa.Enum(
                "NOT_CHECKED",
                "OPENED",
                "CHECKED_NO_JOBS",
                "JOB_FOUND",
                "ERROR",
                name="eures_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            server_default="NOT_CHECKED",
            nullable=False,
        ),
        sa.Column("eures_last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eures_notes", sa.Text(), nullable=True),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("careers_url", sa.Text(), nullable=True),
        sa.Column("ats_provider", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
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
            "eures_status IN ('NOT_CHECKED', 'OPENED', 'CHECKED_NO_JOBS', 'JOB_FOUND', 'ERROR')",
            name=op.f("ck_companies_eures_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
        sa.UniqueConstraint("cvr", name=op.f("uq_companies_cvr")),
    )
    op.create_index(op.f("ix_companies_eures_status"), "companies", ["eures_status"], unique=False)
    op.create_index(
        op.f("ix_companies_normalized_name"), "companies", ["normalized_name"], unique=False
    )
    op.create_index(
        op.f("ix_companies_source_position"), "companies", ["source_position"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_companies_source_position"), table_name="companies")
    op.drop_index(op.f("ix_companies_normalized_name"), table_name="companies")
    op.drop_index(op.f("ix_companies_eures_status"), table_name="companies")
    op.drop_table("companies")
