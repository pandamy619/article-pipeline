"""Применение рерайта: filtered -> drafted с готовым постом."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.collectors.base import Article
from src.db.models import ArticleRecord, ArticleStatus
from src.rewrite.post import Generator, generate_post


@dataclass(slots=True)
class RewriteResult:
    drafted: int


def apply_rewrite(
    session: Session,
    client: Generator,
    *,
    channel_id: int | None = None,
    limit: int | None = None,
) -> RewriteResult:
    """Генерит пост для каждой статьи filtered и переводит её в drafted."""
    stmt = select(ArticleRecord).where(ArticleRecord.status == ArticleStatus.filtered)
    if channel_id is not None:
        stmt = stmt.where(ArticleRecord.channel_id == channel_id)
    if limit:
        stmt = stmt.limit(limit)
    records = session.scalars(stmt).all()

    drafted = 0
    for rec in records:
        art = Article(
            title=rec.title,
            url=rec.url,
            text=rec.text,
            source=rec.source,
            published_at=rec.published_at,
        )
        rec.post_text = generate_post(art, client=client)
        rec.status = ArticleStatus.drafted
        drafted += 1

    session.flush()
    return RewriteResult(drafted=drafted)
