"""article embedding for semantic dedup

Revision ID: 0003_embedding
Revises: 0002_relevance
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_embedding"
down_revision: str | None = "0002_relevance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("articles") as batch:
        batch.add_column(sa.Column("embedding", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("articles") as batch:
        batch.drop_column("embedding")
