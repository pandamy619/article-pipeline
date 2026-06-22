from sqlalchemy import select

from src.db.models import ArticleRecord, ArticleStatus
from src.dedup.semantic import apply_semantic_dedup, cosine


def _add(session, title, text, url):
    session.add(
        ArticleRecord(
            url=url,
            content_hash=url,
            title=title,
            text=text,
            status=ArticleStatus.new,
        )
    )


class FakeEmbedder:
    def embed(self, text: str) -> list[float]:
        if "alpha" in text:
            return [1.0, 0.0]
        if "beta" in text:
            return [0.0, 1.0]
        return [0.5, 0.5]


class BoomEmbedder:
    def embed(self, text: str) -> list[float]:
        raise RuntimeError("no embed model")


def test_cosine():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine([], [1.0]) == 0.0


def test_semantic_dedup_marks_duplicate(session):
    _add(session, "A", "topic alpha", "u1")
    _add(session, "A again", "topic alpha repeated", "u2")
    _add(session, "B", "topic beta", "u3")
    session.flush()

    res = apply_semantic_dedup(session, FakeEmbedder(), threshold=0.88)
    assert res.checked == 3
    assert res.duplicates == 1

    by_url = {r.url: r for r in session.scalars(select(ArticleRecord)).all()}
    assert by_url["u1"].status == ArticleStatus.new
    assert by_url["u1"].embedding is not None
    assert by_url["u2"].status == ArticleStatus.rejected
    assert "дубликат" in by_url["u2"].relevance_reason
    assert by_url["u3"].status == ArticleStatus.new


def test_semantic_dedup_survives_embed_failure(session):
    _add(session, "X", "something", "ux")
    session.flush()

    res = apply_semantic_dedup(session, BoomEmbedder())
    assert res.duplicates == 0
    rec = session.scalars(select(ArticleRecord)).first()
    assert rec.status == ArticleStatus.new
