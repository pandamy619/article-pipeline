"""collect_jobs.query (web-search jobs on the worker)

Revision ID: 0013_collect_job_query
Revises: 0012_collect_jobs
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_collect_job_query"
down_revision: str | None = "0012_collect_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("collect_jobs") as batch:
        batch.add_column(sa.Column("query", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("collect_jobs") as batch:
        batch.drop_column("query")
