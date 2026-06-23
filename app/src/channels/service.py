"""Каналы: CRUD и дефолтный канал из .env."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import Settings, settings
from src.db.models import ArticleRecord, Channel

FIELDS = {
    "name",
    "bot_token",
    "channel_id",
    "admin_user_id",
    "topic",
    "enabled",
    "relevance_threshold",
    "publish_interval_minutes",
    "collect_enabled",
    "collect_interval_minutes",
    "rss_feeds",
    "habr_enabled",
    "habr_hubs",
    "arxiv_categories",
    "reddit_subreddits",
    "searxng_queries",
}


def split(raw: str) -> list[str]:
    return Settings._split(raw or "")


def _clean(fields: dict) -> dict:
    return {k: v for k, v in fields.items() if k in FIELDS}


def list_channels(session: Session) -> Sequence[Channel]:
    return session.scalars(select(Channel).order_by(Channel.id)).all()


def get_channel(session: Session, channel_id: int) -> Channel | None:
    return session.get(Channel, channel_id)


def create_channel(session: Session, **fields) -> Channel:
    ch = Channel(**_clean(fields))
    session.add(ch)
    session.flush()
    return ch


def update_channel(session: Session, channel_id: int, **fields) -> Channel | None:
    ch = session.get(Channel, channel_id)
    if not ch:
        return None
    for key, value in _clean(fields).items():
        setattr(ch, key, value)
    session.flush()
    return ch


def delete_channel(session: Session, channel_id: int) -> bool:
    ch = session.get(Channel, channel_id)
    if not ch:
        return False
    orphans = session.scalars(
        select(ArticleRecord).where(ArticleRecord.channel_id == channel_id)
    ).all()
    for art in orphans:
        art.channel_id = None
    session.delete(ch)
    session.flush()
    return True


def ensure_default_channel(session: Session) -> Channel:
    """Создаёт канал из .env, если каналов ещё нет, и привязывает к нему сирот."""
    existing = session.scalar(select(Channel).order_by(Channel.id))
    if existing:
        return existing
    ch = Channel(
        name="Основной",
        bot_token=settings.telegram_bot_token,
        channel_id=settings.telegram_channel_id,
        admin_user_id=settings.admin_user_id,
        topic=settings.channel_topic,
        enabled=True,
        relevance_threshold=settings.relevance_threshold,
        publish_interval_minutes=settings.publish_interval_minutes,
        collect_enabled=True,
        collect_interval_minutes=settings.run_interval_minutes,
        rss_feeds=settings.rss_feeds,
        habr_enabled=settings.habr_enabled,
        habr_hubs=settings.habr_hubs,
        arxiv_categories=settings.arxiv_categories,
        reddit_subreddits=settings.reddit_subreddits,
        searxng_queries=settings.searxng_queries,
    )
    session.add(ch)
    session.flush()
    orphans = session.scalars(
        select(ArticleRecord).where(ArticleRecord.channel_id.is_(None))
    ).all()
    for art in orphans:
        art.channel_id = ch.id
    session.flush()
    return ch
