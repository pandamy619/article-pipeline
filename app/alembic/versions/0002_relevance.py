"""relevance score and reason

Revision ID: 0002_relevance
Revises: 0001_initial
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_relevance"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("articles") as batch:
        batch.add_column(sa.Column("relevance_score", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("relevance_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("articles") as batch:
        batch.drop_column("relevance_reason")
        batch.drop_column("relevance_score")
