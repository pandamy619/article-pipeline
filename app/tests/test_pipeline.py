from src.collectors.base import Article
from src.db.models import ArticleRecord, ArticleStatus, Channel, RunLog
from src.pipeline import run_pipeline


class FakeLLM:
    """Фильтр (score-JSON) и рерайт (post-JSON) различаем по system-промпту."""

    def generate(self, prompt, *, system=None, format=None):
        if system and '"post"' in system:
            return '{"post": "Пост для новичков #python"}'
        return '{"score": 9, "reason": "ok"}'


def _channel(session):
    ch = Channel(name="t", topic="тема", relevance_threshold=7)
    session.add(ch)
    session.flush()
    return ch


def fake_collector(channel):
    return [
        Article("Python с нуля", "https://e.com/1", "основы для новичков", "src"),
        Article("Ещё статья", "https://e.com/2", "тоже основы", "src"),
    ]


def test_run_pipeline_end_to_end(session):
    ch = _channel(session)
    result = run_pipeline(session, FakeLLM(), ch, collector=fake_collector)
    assert result.collected == 2
    assert result.added == 2
    assert result.filtered == 2
    assert result.rejected == 0
    assert result.drafted == 2

    drafts = session.query(ArticleRecord).filter_by(status=ArticleStatus.drafted).all()
    assert len(drafts) == 2
    assert all(d.post_text and "Источник:" in d.post_text for d in drafts)
    assert all(d.channel_id == ch.id for d in drafts)


def test_run_pipeline_respects_max(session, monkeypatch):
    import src.config

    monkeypatch.setattr(src.config.settings, "max_articles_per_run", 1)
    ch = _channel(session)

    def collector3(channel):
        return [
            Article("a", "https://e.com/1", "x", "s"),
            Article("b", "https://e.com/2", "x", "s"),
            Article("c", "https://e.com/3", "x", "s"),
        ]

    result = run_pipeline(session, FakeLLM(), ch, collector=collector3)
    assert result.collected == 1


def test_run_pipeline_dedup_on_second_run(session):
    ch = _channel(session)
    run_pipeline(session, FakeLLM(), ch, collector=fake_collector)
    result = run_pipeline(session, FakeLLM(), ch, collector=fake_collector)
    assert result.added == 0
    assert result.duplicates == 2
    assert result.drafted == 0


def test_run_pipeline_reports_progress(session):
    ch = _channel(session)
    events: list[tuple[str, int, int]] = []
    run_pipeline(
        session,
        FakeLLM(),
        ch,
        collector=fake_collector,
        on_progress=lambda s, d, t: events.append((s, d, t)),
    )
    stages = [e[0] for e in events]
    assert stages[0] == "collect"
    assert "filter" in stages and "rewrite" in stages
    assert stages[-1] == "done"
    # по-статейный счётчик фильтра доходит до total (2/2)
    filt = [e for e in events if e[0] == "filter"]
    assert (2, 2) in [(e[1], e[2]) for e in filt]


def test_run_pipeline_writes_run_log(session):
    ch = _channel(session)
    run_pipeline(session, FakeLLM(), ch, collector=fake_collector)
    logs = session.query(RunLog).all()
    assert len(logs) == 1
    assert logs[0].ok is True
    assert logs[0].drafted == 2
    assert logs[0].collected == 2
