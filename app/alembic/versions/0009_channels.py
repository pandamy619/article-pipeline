"""channels table + articles.channel_id

Revision ID: 0009_channels
Revises: 0008_app_settings
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_channels"
down_revision: str | None = "0008_app_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("bot_token", sa.String(255), nullable=False, server_default=""),
        sa.Column("channel_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("admin_user_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("topic", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "relevance_threshold", sa.Integer(), nullable=False, server_default="7"
        ),
        sa.Column(
            "publish_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="120",
        ),
        sa.Column("rss_feeds", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "habr_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("habr_hubs", sa.Text(), nullable=False, server_default=""),
        sa.Column("arxiv_categories", sa.Text(), nullable=False, server_default=""),
        sa.Column("reddit_subreddits", sa.Text(), nullable=False, server_default=""),
        sa.Column("searxng_queries", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    with op.batch_alter_table("articles") as batch:
        batch.add_column(sa.Column("channel_id", sa.Integer(), nullable=True))
        batch.create_index("ix_articles_channel_id", ["channel_id"])
        batch.create_foreign_key(
            "fk_articles_channel", "channels", ["channel_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("articles") as batch:
        batch.drop_constraint("fk_articles_channel", type_="foreignkey")
        batch.drop_index("ix_articles_channel_id")
        batch.drop_column("channel_id")
    op.drop_table("channels")
