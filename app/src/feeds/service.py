"""Управление RSS-лентами в рантайме (БД), поверх базовых из .env."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.db.models import Feed


def list_feeds(session: Session, *, only_enabled: bool = False) -> Sequence[Feed]:
    stmt = select(Feed).order_by(Feed.id)
    if only_enabled:
        stmt = stmt.where(Feed.enabled.is_(True))
    return session.scalars(stmt).all()


def add_feed(session: Session, url: str) -> Feed | None:
    url = url.strip()
    if not url:
        return None
    existing = session.scalar(select(Feed).where(Feed.url == url))
    if existing:
        return existing
    feed = Feed(url=url, enabled=True)
    session.add(feed)
    session.flush()
    return feed


def remove_feed(session: Session, feed_id: int) -> bool:
    feed = session.get(Feed, feed_id)
    if not feed:
        return False
    session.delete(feed)
    session.flush()
    return True


def set_enabled(session: Session, feed_id: int, enabled: bool) -> bool:
    feed = session.get(Feed, feed_id)
    if not feed:
        return False
    feed.enabled = enabled
    session.flush()
    return True


def effective_feeds(session: Session) -> list[str]:
    """Базовые ленты из .env + включённые ленты из БД, без дублей (порядок сохраняем)."""
    urls: list[str] = []
    seen: set[str] = set()
    db_urls = [f.url for f in list_feeds(session, only_enabled=True)]
    for url in [*settings.rss_feed_list, *db_urls]:
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls
