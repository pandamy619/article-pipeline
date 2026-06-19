"""initial articles table

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

article_status = sa.Enum(
    "new",
    "filtered",
    "drafted",
    "pending",
    "published",
    "rejected",
    name="article_status",
    native_enum=False,
    length=16,
)


def upgrade() -> None:
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", article_status, nullable=False, server_default="new"),
        sa.Column("post_text", sa.Text(), nullable=True),
        sa.Column("tg_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_articles_url", "articles", ["url"], unique=True)
    op.create_index(
        "ix_articles_content_hash", "articles", ["content_hash"], unique=True
    )
    op.create_index("ix_articles_status", "articles", ["status"])


def downgrade() -> None:
    op.drop_index("ix_articles_status", table_name="articles")
    op.drop_index("ix_articles_content_hash", table_name="articles")
    op.drop_index("ix_articles_url", table_name="articles")
    op.drop_table("articles")
