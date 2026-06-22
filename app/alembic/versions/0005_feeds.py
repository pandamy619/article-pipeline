"""feeds table (runtime-managed RSS)

Revision ID: 0005_feeds
Revises: 0004_image
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_feeds"
down_revision: str | None = "0004_image"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feeds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_feeds_url", "feeds", ["url"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_feeds_url", table_name="feeds")
    op.drop_table("feeds")
