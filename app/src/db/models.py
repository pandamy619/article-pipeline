"""ORM-модели и статусы статьи."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ArticleStatus(str, enum.Enum):
    new = "new"  # только собрана
    filtered = "filtered"  # прошла порог релевантности
    drafted = "drafted"  # сгенерирован пост
    pending = "pending"  # ждёт модерации
    published = "published"
    rejected = "rejected"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ArticleRecord(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
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
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-вектор
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
