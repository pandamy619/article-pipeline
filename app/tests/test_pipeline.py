from src.collectors.base import Article
from src.db.models import ArticleRecord, ArticleStatus, RunLog
from src.pipeline import run_pipeline


class FakeLLM:
    """Фильтр (score-JSON) и рерайт (post-JSON) различаем по system-промпту."""

    def generate(self, prompt, *, system=None, format=None):
        if system and '"post"' in system:
            return '{"post": "Пост для новичков #python"}'
        return '{"score": 9, "reason": "ok"}'


def fake_collector(feeds):
    return [
        Article("Python с нуля", "https://e.com/1", "основы для новичков", "src"),
        Article("Ещё статья", "https://e.com/2", "тоже основы", "src"),
    ]


def test_run_pipeline_end_to_end(session):
    result = run_pipeline(session, FakeLLM(), collector=fake_collector, feeds=[])
    assert result.collected == 2
    assert result.added == 2
    assert result.filtered == 2
    assert result.rejected == 0
    assert result.drafted == 2

    drafts = session.query(ArticleRecord).filter_by(status=ArticleStatus.drafted).all()
    assert len(drafts) == 2
    assert all(d.post_text and "Источник:" in d.post_text for d in drafts)


def test_run_pipeline_respects_max(session, monkeypatch):
    import src.config

    monkeypatch.setattr(src.config.settings, "max_articles_per_run", 1)

    def collector3(feeds):
        return [
            Article("a", "https://e.com/1", "x", "s"),
            Article("b", "https://e.com/2", "x", "s"),
            Article("c", "https://e.com/3", "x", "s"),
        ]

    result = run_pipeline(session, FakeLLM(), collector=collector3, feeds=[])
    assert result.collected == 1


def test_run_pipeline_dedup_on_second_run(session):
    run_pipeline(session, FakeLLM(), collector=fake_collector, feeds=[])
    result = run_pipeline(session, FakeLLM(), collector=fake_collector, feeds=[])
    assert result.added == 0
    assert result.duplicates == 2
    assert result.drafted == 0


def test_run_pipeline_writes_run_log(session):
    run_pipeline(session, FakeLLM(), collector=fake_collector, feeds=[])
    logs = session.query(RunLog).all()
    assert len(logs) == 1
    assert logs[0].ok is True
    assert logs[0].drafted == 2
    assert logs[0].collected == 2
