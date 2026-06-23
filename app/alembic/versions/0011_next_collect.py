"""channel next_collect_at (UI hint for next scheduled collect)

Revision ID: 0011_next_collect
Revises: 0010_collect_schedule
Create Date: 2026-06-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_next_collect"
down_revision: str | None = "0010_collect_schedule"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("channels") as batch:
        batch.add_column(
            sa.Column("next_collect_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("channels") as batch:
        batch.drop_column("next_collect_at")
