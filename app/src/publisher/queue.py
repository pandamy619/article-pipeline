"""Очередь публикации: планирование статей по времени.

Статья с готовым постом ставится в очередь (status=scheduled, scheduled_at).
Фоновый планировщик публикует «созревшие» (scheduled_at <= now).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.db.models import ArticleRecord, ArticleStatus


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


def next_slot(session: Session) -> datetime:
    """Следующий авто-слот: max(сейчас, последний в очереди) + интервал."""
    latest = session.scalar(
        select(ArticleRecord.scheduled_at)
        .where(ArticleRecord.status == ArticleStatus.scheduled)
        .where(ArticleRecord.scheduled_at.is_not(None))
        .order_by(ArticleRecord.scheduled_at.desc())
    )
    now = _now()
    if latest is not None and latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)  # SQLite хранит naive
    base = latest if latest and latest > now else now
    return base + timedelta(minutes=settings.publish_interval_minutes)


def schedule_article(
    session: Session, article_id: int, when: datetime | None = None
) -> datetime | None:
    """Ставит статью в очередь. when=None -> следующий авто-слот."""
    rec = session.get(ArticleRecord, article_id)
    if not rec or not rec.post_text:
        return None
    when = when or next_slot(session)
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
