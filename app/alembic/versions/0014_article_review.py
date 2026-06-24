"""articles.review (web-found, pending approval, hidden from main table)

Revision ID: 0014_article_review
Revises: 0013_collect_job_query
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_article_review"
down_revision: str | None = "0013_collect_job_query"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("articles") as batch:
        batch.add_column(
            sa.Column(
                "review",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    op.create_index("ix_articles_review", "articles", ["review"])


def downgrade() -> None:
    op.drop_index("ix_articles_review", table_name="articles")
    with op.batch_alter_table("articles") as batch:
        batch.drop_column("review")
