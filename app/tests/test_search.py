import json

from src.collectors.base import Article
from src.db.models import ArticleRecord, ArticleStatus, Channel
from src.search import service as ss


class FakeEmbedder:
    def embed(self, text):
        if "alpha" in text:
            return [1.0, 0.0]
        if "beta" in text:
            return [0.0, 1.0]
        return [0.5, 0.5]


def _emb_article(session, url, vec):
    rec = ArticleRecord(
        url=url,
        content_hash=url,
        title=url,
        text="x",
        status=ArticleStatus.filtered,
        embedding=json.dumps(vec),
    )
    session.add(rec)
    session.flush()
    return rec


def test_parse_list():
    assert ss._parse_list('["a","b"]') == ["a", "b"]
    assert ss._parse_list('{"queries":["x"]}') == ["x"]
    assert ss._parse_list("not json") == []


def test_generate_queries_fallback():
    class G:
        def generate(self, prompt, *, system=None, format=None):
            return "garbage"

    assert ss.generate_queries(G(), "тема") == ["тема"]


def test_generate_queries_parsed():
    class G:
        def generate(self, prompt, *, system=None, format=None):
            return '["python для новичков", "git basics"]'

    assert ss.generate_queries(G(), "x", n=2) == ["python для новичков", "git basics"]


def test_semantic_search_ranks(session):
    _emb_article(session, "a", [1.0, 0.0])
    _emb_article(session, "b", [0.0, 1.0])
    results = ss.semantic_search(session, FakeEmbedder(), "topic alpha")
    assert results[0][0].url == "a"
    assert results[0][1] > results[1][1]


def test_web_search_collect(session, monkeypatch):
    ch = Channel(name="c", topic="t", relevance_threshold=7)
    session.add(ch)
    session.flush()

    monkeypatch.setattr(
        ss,
        "collect_websearch",
        lambda queries: [
            Article("T", "https://e.com/x", "основы для новичков", "Веб-поиск")
        ],
    )

    class FakeLLM:
        def generate(self, prompt, *, system=None, format=None):
            if system and "JSON-массивом" in system:
                return '["q1"]'
            if system and '"post"' in system:
                return '{"post": "пост"}'
            return '{"score": 9, "reason": "ok"}'

    added, queries = ss.web_search_collect(
        session, FakeLLM(), "опиши", channel_id=ch.id
    )
    assert added == 1
    assert queries == ["q1"]
    rec = session.query(ArticleRecord).filter_by(url="https://e.com/x").first()
    assert rec.status == ArticleStatus.drafted
    assert rec.channel_id == ch.id
    # веб-находка помечена review=True — ждёт одобрения, не в общей таблице
    assert rec.review is True
