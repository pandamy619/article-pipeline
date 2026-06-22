from datetime import datetime, timedelta, timezone

from src.db.models import ArticleRecord, ArticleStatus
from src.publisher import queue


def _add(session, url, *, post_text="пост", status=ArticleStatus.drafted):
    rec = ArticleRecord(
        url=url,
        content_hash=url,
        title="t",
        text="x",
        status=status,
        post_text=post_text,
    )
    session.add(rec)
    session.flush()
    return rec


def test_parse_when():
    assert queue.parse_when(None) is None
    assert queue.parse_when("") is None
    assert queue.parse_when("2026-06-22T10:00:00Z").tzinfo is not None
    assert queue.parse_when("2026-06-22T10:00:00").tzinfo is not None  # naive -> UTC


def test_schedule_requires_post(session):
    rec = _add(session, "u1", post_text=None, status=ArticleStatus.new)
    assert queue.schedule_article(session, rec.id) is None
    assert rec.status == ArticleStatus.new


def test_schedule_default_slot_spacing(session, monkeypatch):
    import src.config

    monkeypatch.setattr(src.config.settings, "publish_interval_minutes", 60)
    a = _add(session, "a")
    b = _add(session, "b")
    t1 = queue.schedule_article(session, a.id)
    t2 = queue.schedule_article(session, b.id)
    assert a.status == ArticleStatus.scheduled
    assert (t2 - t1) >= timedelta(minutes=59)


def test_unschedule(session):
    a = _add(session, "a")
    queue.schedule_article(session, a.id)
    assert queue.unschedule(session, a.id) is True
    assert a.scheduled_at is None
    assert a.status == ArticleStatus.drafted


def test_due_article_ids(session):
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    future = datetime.now(timezone.utc) + timedelta(hours=5)
    a = _add(session, "a")
    b = _add(session, "b")
    queue.schedule_article(session, a.id, when=past)
    queue.schedule_article(session, b.id, when=future)
    due = queue.due_article_ids(session)
    assert a.id in due
    assert b.id not in due
