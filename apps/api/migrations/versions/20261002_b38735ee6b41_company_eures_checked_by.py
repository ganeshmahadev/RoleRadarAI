"""company eures checked by

Revision ID: b38735ee6b41
Revises: a2c571fad892
Create Date: 2026-10-02 02:40:37.287021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b38735ee6b41"
down_revision: str | None = "a2c571fad892"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("eures_checked_by", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "eures_checked_by")
