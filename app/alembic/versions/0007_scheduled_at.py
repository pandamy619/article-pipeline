"""article scheduled_at (publish queue)

Revision ID: 0007_scheduled_at
Revises: 0006_run_log
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_scheduled_at"
down_revision: str | None = "0006_run_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("articles") as batch:
        batch.add_column(
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("articles") as batch:
        batch.drop_column("scheduled_at")
