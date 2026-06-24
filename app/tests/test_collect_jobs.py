"""Воркер ручного сбора: бот разбирает очередь collect_jobs."""

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.db.base as db_base
from src.db.models import Base, CollectJob, CollectJobStatus
from src.pipeline import PipelineResult


@pytest.fixture()
def memdb(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(db_base, "SessionLocal", factory)
    return factory


def test_drain_marks_job_done(memdb, monkeypatch):
    import src.moderation.bot as bot

    monkeypatch.setattr(bot, "OllamaClient", lambda *a, **k: object())
    monkeypatch.setattr(
        bot,
        "run_all_channels",
        lambda session, client: PipelineResult(3, 2, 1, 0, 1, 0, 1),
    )

    async def _noop() -> int:
        return 0

    monkeypatch.setattr(bot, "send_drafts_all", _noop)

    s = memdb()
    s.add(CollectJob(channel_id=None, status=CollectJobStatus.queued))
    s.commit()
    s.close()

    asyncio.run(bot._drain_collect_jobs())

    s = memdb()
    job = s.query(CollectJob).first()
    assert job.status == CollectJobStatus.done
    assert '"added": 2' in (job.result or "")
    assert job.finished_at is not None
    s.close()


def test_drain_marks_job_error(memdb, monkeypatch):
    import src.moderation.bot as bot

    monkeypatch.setattr(bot, "OllamaClient", lambda *a, **k: object())

    def _boom(session, client):
        raise RuntimeError("LLM недоступен")

    monkeypatch.setattr(bot, "run_all_channels", _boom)

    async def _noop_notify(text: str) -> None:
        return None

    monkeypatch.setattr(bot, "_notify_admin", _noop_notify)

    s = memdb()
    s.add(CollectJob(channel_id=None, status=CollectJobStatus.queued))
    s.commit()
    s.close()

    asyncio.run(bot._drain_collect_jobs())

    s = memdb()
    job = s.query(CollectJob).first()
    assert job.status == CollectJobStatus.error
    assert "LLM недоступен" in (job.error or "")
    s.close()


def test_drain_runs_web_search(memdb, monkeypatch):
    import src.moderation.bot as bot

    monkeypatch.setattr(bot, "OllamaClient", lambda *a, **k: object())
    monkeypatch.setattr(
        bot,
        "web_search_collect",
        lambda session, client, query, *, channel_id=None: (2, ["q1", "q2"]),
    )

    sent = {"n": 0}

    async def _noop() -> int:
        sent["n"] += 1
        return 0

    monkeypatch.setattr(bot, "send_drafts_all", _noop)

    s = memdb()
    s.add(
        CollectJob(
            channel_id=None,
            query="питон асинхронность",
            status=CollectJobStatus.queued,
        )
    )
    s.commit()
    s.close()

    asyncio.run(bot._drain_collect_jobs())

    s = memdb()
    job = s.query(CollectJob).first()
    assert job.status == CollectJobStatus.done
    assert '"added": 2' in (job.result or "")
    assert "q1" in (job.result or "")
    s.close()
    # веб-поиск не должен слать кандидатов в бота
    assert sent["n"] == 0


def test_publish_due_unschedules_on_bad_request(memdb, monkeypatch):
    from datetime import datetime, timezone

    from aiogram.exceptions import TelegramBadRequest

    import src.moderation.bot as bot
    from src.db.models import ArticleRecord, ArticleStatus

    s = memdb()
    s.add(
        ArticleRecord(
            url="https://e.com/p",
            content_hash="ph",
            title="t",
            text="x",
            source="s",
            status=ArticleStatus.scheduled,
            post_text="пост",
            scheduled_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
    )
    s.commit()
    s.close()

    class _Sess:
        async def close(self):
            pass

    class _Bot:
        session = _Sess()

    monkeypatch.setattr(bot, "make_bot", lambda token: _Bot())

    async def _raise(*a, **k):
        raise TelegramBadRequest(method=None, message="chat not found")

    monkeypatch.setattr(bot, "publish", _raise)

    notified: dict[str, str] = {}

    async def _notify(text: str) -> None:
        notified["text"] = text

    monkeypatch.setattr(bot, "_notify_admin", _notify)

    asyncio.run(bot._publish_due())

    s = memdb()
    rec = s.query(ArticleRecord).first()
    assert rec.status == ArticleStatus.drafted  # снят с очереди
    assert rec.scheduled_at is None
    s.close()
    assert "chat not found" in notified["text"]


def test_drain_noop_when_empty(memdb, monkeypatch):
    import src.moderation.bot as bot

    called = {"n": 0}

    def _count(session, client):  # не должно вызваться — очередь пуста
        called["n"] += 1
        return PipelineResult(0, 0, 0, 0, 0, 0, 0)

    monkeypatch.setattr(bot, "run_all_channels", _count)
    monkeypatch.setattr(bot, "OllamaClient", lambda *a, **k: object())

    asyncio.run(bot._drain_collect_jobs())
    assert called["n"] == 0
