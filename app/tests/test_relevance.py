import json

import httpx

from src.collectors.base import Article
from src.db.models import ArticleRecord, ArticleStatus
from src.db.repo import save_articles
from src.filter.relevance import RelevanceResult, _parse, is_relevant, score_relevance
from src.filter.service import apply_relevance_filter
from src.llm.client import OllamaClient


class FakeScorer:
    def __init__(self, score, reason="ok"):
        self.payload = json.dumps({"score": score, "reason": reason})
        self.last_format = None

    def generate(self, prompt, *, system=None, format=None):
        self.last_format = format
        return self.payload


def test_score_relevance_parses():
    c = FakeScorer(8, "норм для новичка")
    r = score_relevance(Article("t", "u", "body", "src"), client=c)
    assert r.score == 8
    assert r.reason == "норм для новичка"
    assert c.last_format == "json"  # просим структурный ответ


def test_parse_bad_json():
    assert _parse("это не json").score == 0


def test_parse_clamps_range():
    assert _parse(json.dumps({"score": 99})).score == 10
    assert _parse(json.dumps({"score": -5})).score == 0


def test_is_relevant_threshold():
    assert is_relevant(RelevanceResult(7, ""), threshold=7)
    assert not is_relevant(RelevanceResult(6, ""), threshold=7)


def test_ollama_client_generate():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert request.url.path == "/api/generate"
        assert body["stream"] is False
        assert body["format"] == "json"
        return httpx.Response(200, json={"response": '{"score": 5}'})

    client = OllamaClient(
        host="http://x", model="m", transport=httpx.MockTransport(handler)
    )
    assert client.generate("p", system="s", format="json") == '{"score": 5}'


def test_apply_relevance_filter(session):
    save_articles(
        session,
        [
            Article("Python для новичков", "u1", "основы программирования", "src"),
            Article("Linux kernel internals", "u2", "глубокий хардкор", "src"),
        ],
    )

    class ByText:
        def generate(self, prompt, *, system=None, format=None):
            score = 9 if "основы" in prompt else 2
            return json.dumps({"score": score, "reason": "x"})

    res = apply_relevance_filter(session, ByText(), threshold=7)
    assert res.filtered == 1
    assert res.rejected == 1

    rows = {r.url: r for r in session.query(ArticleRecord).all()}
    assert rows["u1"].status == ArticleStatus.filtered
    assert rows["u2"].status == ArticleStatus.rejected
    assert rows["u1"].relevance_score == 9
    assert rows["u2"].relevance_score == 2
