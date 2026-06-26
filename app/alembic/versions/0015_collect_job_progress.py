"""collect_jobs.progress (stage + per-article counter for the UI)

Revision ID: 0015_collect_job_progress
Revises: 0014_article_review
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_collect_job_progress"
down_revision: str | None = "0014_article_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("collect_jobs") as batch:
        batch.add_column(sa.Column("progress", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("collect_jobs") as batch:
        batch.drop_column("progress")
