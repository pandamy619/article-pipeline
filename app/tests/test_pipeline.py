from src.collectors.base import Article
from src.db.models import ArticleRecord, ArticleStatus
from src.pipeline import run_pipeline


class FakeLLM:
    """Возвращает score-JSON для фильтра и текст поста для рерайта."""

    def generate(self, prompt, *, system=None, format=None):
        if format == "json":
            return '{"score": 9, "reason": "ok"}'
        return "Заголовок поста\n\nкороткий текст #python"


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


def test_run_pipeline_dedup_on_second_run(session):
    run_pipeline(session, FakeLLM(), collector=fake_collector, feeds=[])
    result = run_pipeline(session, FakeLLM(), collector=fake_collector, feeds=[])
    assert result.added == 0
    assert result.duplicates == 2
    assert result.drafted == 0
