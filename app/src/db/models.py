"""ORM-модели и статусы статьи."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ArticleStatus(str, enum.Enum):
    new = "new"  # только собрана
    filtered = "filtered"  # прошла порог релевантности
    drafted = "drafted"  # сгенерирован пост
    pending = "pending"  # ждёт модерации
    scheduled = "scheduled"  # в очереди на публикацию по времени
    published = "published"
    rejected = "rejected"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ArticleRecord(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("channels.id"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(1024), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(512), default="")
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[ArticleStatus] = mapped_column(
        Enum(ArticleStatus, native_enum=False, length=16),
        default=ArticleStatus.new,
        index=True,
    )
    relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-вектор
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Feed(Base):
    """RSS-лента, управляемая в рантайме (через бота/админку), помимо .env."""

    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class RunLog(Base):
    """Итоги одного прогона пайплайна — для метрик и мониторинга ошибок."""

    __tablename__ = "run_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    collected: Mapped[int] = mapped_column(Integer, default=0)
    added: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    semantic_duplicates: Mapped[int] = mapped_column(Integer, default=0)
    filtered: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    drafted: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AppSetting(Base):
    """Рантайм-настройка (key/value) поверх .env, редактируется из админки."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Channel(Base):
    """Телеграм-канал со своим ботом, тематикой и источниками."""

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    bot_token: Mapped[str] = mapped_column(String(255), default="")
    channel_id: Mapped[str] = mapped_column(String(255), default="")  # @name или -100…
    admin_user_id: Mapped[str] = mapped_column(String(64), default="")
    topic: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    relevance_threshold: Mapped[int] = mapped_column(Integer, default=7)
    publish_interval_minutes: Mapped[int] = mapped_column(Integer, default=120)
    collect_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    collect_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    next_collect_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # подсказка для UI: когда планировщик бота запустит сбор в следующий раз
    rss_feeds: Mapped[str] = mapped_column(Text, default="")
    habr_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    habr_hubs: Mapped[str] = mapped_column(Text, default="")
    arxiv_categories: Mapped[str] = mapped_column(Text, default="")
    reddit_subreddits: Mapped[str] = mapped_column(Text, default="")
    searxng_queries: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
