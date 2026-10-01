"""discovery runs and source types

Revision ID: a2c571fad892
Revises: 2c4db9b939ad
Create Date: 2026-10-02 02:32:02.248374
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2c571fad892"
down_revision: str | None = "2c4db9b939ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_TYPES = "'jsonld', 'greenhouse', 'lever', 'ashby', 'generic_html', 'manual'"
NEW_TYPES = OLD_TYPES + ", 'indeed', 'linkedin', 'google', 'eures'"


def upgrade() -> None:
    op.create_table(
        "discovery_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "search_terms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("location", sa.Text(), server_default="Denmark", nullable=False),
        sa.Column(
            "sites",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default='["indeed", "linkedin", "google"]',
            nullable=False,
        ),
        sa.Column("results_per_site", sa.Integer(), server_default="25", nullable=False),
        sa.Column("hours_old", sa.Integer(), server_default="72", nullable=False),
        sa.Column("eures_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("eures_companies_per_run", sa.Integer(), server_default="120", nullable=False),
        sa.Column("scrape_budget_minutes", sa.Integer(), server_default="20", nullable=False),
        sa.Column("total_budget_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discovery_settings")),
    )
    op.create_table(
        "discovery_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "trigger",
            sa.Enum(
                "manual",
                "scheduled",
                name="discovery_trigger",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "RUNNING",
                "DONE",
                "CANCELLED",
                "FAILED",
                name="discovery_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "phase",
            sa.Enum(
                "QUEUED",
                "SCRAPING",
                "EURES",
                "SCORING",
                "FINISHED",
                name="discovery_phase",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "sources", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column(
            "new_jobs", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("match_run_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scrape_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "phase IN ('QUEUED', 'SCRAPING', 'EURES', 'SCORING', 'FINISHED')",
            name=op.f("ck_discovery_runs_discovery_phase"),
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'DONE', 'CANCELLED', 'FAILED')",
            name=op.f("ck_discovery_runs_discovery_status"),
        ),
        sa.CheckConstraint(
            "trigger IN ('manual', 'scheduled')", name=op.f("ck_discovery_runs_discovery_trigger")
        ),
        sa.ForeignKeyConstraint(
            ["match_run_id"],
            ["match_runs.id"],
            name=op.f("fk_discovery_runs_match_run_id_match_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discovery_runs")),
    )
    op.create_index(op.f("ix_discovery_runs_status"), "discovery_runs", ["status"], unique=False)
    # New discovery source types (PRD §84). Alembic does not compare CHECK constraints.
    for table in ("jobs", "job_sources"):
        op.drop_constraint(op.f(f"ck_{table}_source_type"), table, type_="check")
        op.create_check_constraint(
            op.f(f"ck_{table}_source_type"),
            table,
            f"source_type IN ({NEW_TYPES})",
        )


def downgrade() -> None:
    # Fails if discovered jobs exist (their source types would violate the old list).
    for table in ("jobs", "job_sources"):
        op.drop_constraint(op.f(f"ck_{table}_source_type"), table, type_="check")
        op.create_check_constraint(
            op.f(f"ck_{table}_source_type"),
            table,
            f"source_type IN ({OLD_TYPES})",
        )
    op.drop_index(op.f("ix_discovery_runs_status"), table_name="discovery_runs")
    op.drop_table("discovery_runs")
    op.drop_table("discovery_settings")
