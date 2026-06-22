"""article image_url

Revision ID: 0004_image
Revises: 0003_embedding
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_image"
down_revision: str | None = "0003_embedding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("articles") as batch:
        batch.add_column(sa.Column("image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("articles") as batch:
        batch.drop_column("image_url")
