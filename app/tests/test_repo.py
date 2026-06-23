from datetime import datetime, timezone

from src.collectors.base import Article
from src.db.models import ArticleRecord, ArticleStatus
from src.db.repo import save_articles


def _art(url, title="Заголовок", text="тело статьи"):
    return Article(
        title=title,
        url=url,
        text=text,
        source="src",
        published_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )


def test_save_new(session):
    res = save_articles(
        session,
        [_art("https://e.com/1"), _art("https://e.com/2", title="T2", text="b2")],
    )
    assert res.added == 2
    assert res.duplicates == 0
    assert session.query(ArticleRecord).count() == 2
    assert session.query(ArticleRecord).first().status == ArticleStatus.new


def test_dedup_by_url(session):
    save_articles(session, [_art("https://e.com/1")])
    res = save_articles(
        session, [_art("https://e.com/1", title="другое", text="другое")]
    )
    assert res.added == 0
    assert res.duplicates == 1
    assert session.query(ArticleRecord).count() == 1


def test_dedup_by_content_hash(session):
    save_articles(session, [_art("https://e.com/1", title="Одно", text="То же тело")])
    # другой URL, идентичный контент -> дубль по хешу
    res = save_articles(
        session, [_art("https://e.com/2", title="Одно", text="То же тело")]
    )
    assert res.added == 0
    assert res.duplicates == 1


def test_dedup_within_batch(session):
    res = save_articles(session, [_art("https://e.com/1"), _art("https://e.com/1")])
    assert res.added == 1
    assert res.duplicates == 1


def test_unique_race_counts_as_duplicate(session, monkeypatch):
    # url уже в БД
    assert save_articles(session, [_art("https://e.com/race")]).added == 1
    session.commit()

    # эмулируем гонку: пречек "не нашёл", хотя строка уже есть (как будто её
    # вставил параллельный прогон между проверкой и flush)
    import src.db.repo as repo

    monkeypatch.setattr(repo, "_existing_id", lambda *a, **k: None)

    # SAVEPOINT ловит UniqueViolation -> дубль, без падения всего прогона
    res = save_articles(
        session, [_art("https://e.com/race", title="другое", text="другое тело")]
    )
    assert res.added == 0
    assert res.duplicates == 1
    assert session.query(ArticleRecord).count() == 1
