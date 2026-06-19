"""Сохранение статей с дедупликацией."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
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


def save_articles(session: Session, articles: Iterable[Article]) -> SaveResult:
    """Сохраняет новые статьи, пропуская дубли по URL и по хешу контента."""
    added = 0
    duplicates = 0
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()

    for art in articles:
        h = content_hash(art.title, art.text)
        if art.url in seen_urls or h in seen_hashes:
            duplicates += 1
            continue

        exists = session.scalar(
            select(ArticleRecord.id).where(
                (ArticleRecord.url == art.url) | (ArticleRecord.content_hash == h)
            )
        )
        seen_urls.add(art.url)
        seen_hashes.add(h)
        if exists:
            duplicates += 1
            continue

        session.add(
            ArticleRecord(
                url=art.url,
                content_hash=h,
                title=art.title,
                text=art.text,
                source=art.source,
                published_at=art.published_at,
                status=ArticleStatus.new,
            )
        )
        added += 1

    session.flush()
    return SaveResult(added=added, duplicates=duplicates)
