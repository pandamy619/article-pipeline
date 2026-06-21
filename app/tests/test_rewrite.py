import json

from src.collectors.base import Article
from src.db.models import ArticleRecord, ArticleStatus
from src.db.repo import save_articles
from src.rewrite.post import _assemble, _extract_post, generate_post
from src.rewrite.service import apply_rewrite


class FakeGen:
    def __init__(self, body):
        self.body = body
        self.last_format = None

    def generate(self, prompt, *, system=None, format=None):
        self.last_format = format
        return json.dumps({"post": self.body})


def test_extract_post_handles_json_and_plain():
    assert _extract_post('{"post": "привет"}') == "привет"
    assert _extract_post("просто текст") == "просто текст"


def test_extract_post_truncated_json():
    # обрезанный по лимиту токенов JSON (нет закрывающей кавычки и скобки)
    assert _extract_post('{"post": "привет мир') == "привет мир"
    assert _extract_post('{"post": "строка\\nещё"}') == "строка\nещё"


def test_generate_post_appends_source():
    art = Article("T", "https://e.com/a", "тело", "src")
    post = generate_post(art, client=FakeGen("Заголовок\n\nКороткий текст #python"))
    assert "Заголовок" in post
    assert "Источник: https://e.com/a" in post


def test_assemble_trims_to_limit():
    post = _assemble("x" * 5000, "https://e.com/a", limit=200)
    assert len(post) <= 200
    assert post.endswith("Источник: https://e.com/a")
    assert "…" in post


def test_apply_rewrite_sets_drafted(session):
    save_articles(session, [Article("Python", "u1", "основы", "src")])
    rec = session.query(ArticleRecord).one()
    rec.status = ArticleStatus.filtered
    session.flush()

    res = apply_rewrite(session, FakeGen("Пост про Python\n\nПолезно новичкам #python"))
    assert res.drafted == 1
    rec = session.query(ArticleRecord).one()
    assert rec.status == ArticleStatus.drafted
    assert rec.post_text and "Источник: u1" in rec.post_text


def test_apply_rewrite_ignores_non_filtered(session):
    save_articles(session, [Article("X", "u2", "t", "src")])  # статус new
    res = apply_rewrite(session, FakeGen("body"))
    assert res.drafted == 0
