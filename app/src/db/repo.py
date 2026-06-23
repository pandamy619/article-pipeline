"""Сохранение статей с дедупликацией."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.collectors.base import Article
from src.db.models import ArticleRecord, ArticleStatus


def content_hash(title: str, text: str) -> str:
    """SHA-256 от нормализованного контента — ловит дубли с разными URL."""
    payload = f"{title.strip()}\n{text.strip()}".encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(slots=True)
class SaveResult:
    added: int
    duplicates: int


def _existing_id(session: Session, url: str, content_hash_: str) -> int | None:
    """id уже сохранённой статьи с таким URL или хешом контента, иначе None."""
    return session.scalar(
        select(ArticleRecord.id).where(
            (ArticleRecord.url == url) | (ArticleRecord.content_hash == content_hash_)
        )
    )


def save_articles(
    session: Session, articles: Iterable[Article], *, channel_id: int | None = None
) -> SaveResult:
    """Сохраняет новые статьи, пропуская дубли по URL и по хешу контента.

    Вставка каждой статьи идёт в отдельном SAVEPOINT: если параллельный прогон
    (плановый сбор + ручной запуск, либо два проекта с общей лентой) успел
    вставить тот же url/hash между проверкой и flush, это считается дублем, а не
    роняет весь прогон конфликтом уникального индекса.
    """
    added = 0
    duplicates = 0
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()

    for art in articles:
        h = content_hash(art.title, art.text)
        if art.url in seen_urls or h in seen_hashes:
            duplicates += 1
            continue
        seen_urls.add(art.url)
        seen_hashes.add(h)

        if _existing_id(session, art.url, h) is not None:
            duplicates += 1
            continue

        rec = ArticleRecord(
            channel_id=channel_id,
            url=art.url,
            content_hash=h,
            title=art.title,
            text=art.text,
            source=art.source,
            published_at=art.published_at,
            image_url=art.image_url,
            status=ArticleStatus.new,
        )
        try:
            with session.begin_nested():
                session.add(rec)
                session.flush()
        except IntegrityError:
            # гонка по уникальному url/content_hash — статью уже сохранил
            # параллельный прогон; SAVEPOINT откатился, считаем дублем
            duplicates += 1
            continue
        added += 1

    return SaveResult(added=added, duplicates=duplicates)
