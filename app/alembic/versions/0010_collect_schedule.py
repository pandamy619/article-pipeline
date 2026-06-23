"""per-channel collect schedule (collect_enabled, collect_interval_minutes)

Revision ID: 0010_collect_schedule
Revises: 0009_channels
Create Date: 2026-06-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_collect_schedule"
down_revision: str | None = "0009_channels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("channels") as batch:
        batch.add_column(
            sa.Column(
                "collect_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch.add_column(
            sa.Column(
                "collect_interval_minutes",
                sa.Integer(),
                nullable=False,
                server_default="60",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("channels") as batch:
        batch.drop_column("collect_interval_minutes")
        batch.drop_column("collect_enabled")
