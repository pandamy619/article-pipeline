"""Очередь публикации: планирование статей по времени.

Статья с готовым постом ставится в очередь (status=scheduled, scheduled_at).
Фоновый планировщик публикует «созревшие» (scheduled_at <= now).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.db.models import ArticleRecord, ArticleStatus, Channel


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_when(value: str | None) -> datetime | None:
    """ISO-строка -> aware datetime (UTC). Терпит 'Z' и naive (считаем UTC)."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _channel_interval(session: Session, channel_id: int | None) -> int:
    """Интервал публикации проекта (мин); фолбэк — глобальный из настроек."""
    if channel_id is not None:
        ch = session.get(Channel, channel_id)
        if ch and ch.publish_interval_minutes:
            return ch.publish_interval_minutes
    return settings.publish_interval_minutes


def next_slot(
    session: Session, channel_id: int | None, interval_minutes: int
) -> datetime:
    """Следующий авто-слот в очереди ПРОЕКТА: max(сейчас, последний) + интервал."""
    stmt = (
        select(ArticleRecord.scheduled_at)
        .where(ArticleRecord.status == ArticleStatus.scheduled)
        .where(ArticleRecord.scheduled_at.is_not(None))
        .order_by(ArticleRecord.scheduled_at.desc())
    )
    if channel_id is not None:
        stmt = stmt.where(ArticleRecord.channel_id == channel_id)
    latest = session.scalar(stmt)
    now = _now()
    if latest is not None and latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)  # SQLite хранит naive
    base = latest if latest and latest > now else now
    return base + timedelta(minutes=interval_minutes)


def schedule_article(
    session: Session, article_id: int, when: datetime | None = None
) -> datetime | None:
    """Ставит статью в очередь. when=None -> авто-слот по интервалу её проекта."""
    rec = session.get(ArticleRecord, article_id)
    if not rec or not rec.post_text:
        return None
    if when is None:
        interval = _channel_interval(session, rec.channel_id)
        when = next_slot(session, rec.channel_id, interval)
    rec.scheduled_at = when
    rec.status = ArticleStatus.scheduled
    session.flush()
    return when


def unschedule(session: Session, article_id: int) -> bool:
    rec = session.get(ArticleRecord, article_id)
    if not rec:
        return False
    rec.scheduled_at = None
    if rec.status == ArticleStatus.scheduled:
        rec.status = ArticleStatus.drafted
    session.flush()
    return True


def due_article_ids(session: Session) -> list[int]:
    """ID статей, у которых подошло время публикации."""
    rows = session.scalars(
        select(ArticleRecord.id)
        .where(ArticleRecord.status == ArticleStatus.scheduled)
        .where(ArticleRecord.scheduled_at.is_not(None))
        .where(ArticleRecord.scheduled_at <= _now())
        .order_by(ArticleRecord.scheduled_at)
    ).all()
    return list(rows)
