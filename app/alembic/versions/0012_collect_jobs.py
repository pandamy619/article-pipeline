"""collect_jobs queue (manual collect via worker)

Revision ID: 0012_collect_jobs
Revises: 0011_next_collect
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_collect_jobs"
down_revision: str | None = "0011_next_collect"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collect_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_collect_jobs_status", "collect_jobs", ["status"])
    op.create_index("ix_collect_jobs_created_at", "collect_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_collect_jobs_created_at", table_name="collect_jobs")
    op.drop_index("ix_collect_jobs_status", table_name="collect_jobs")
    op.drop_table("collect_jobs")
