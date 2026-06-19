"""Применение фильтра релевантности к статьям в БД."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.collectors.base import Article
from src.config import settings
from src.db.models import ArticleRecord, ArticleStatus
from src.filter.relevance import Scorer, score_relevance


@dataclass(slots=True)
class FilterResult:
    filtered: int
    rejected: int


def apply_relevance_filter(
    session: Session, client: Scorer, *, threshold: int | None = None
) -> FilterResult:
    """Оценивает все статьи со статусом new и проставляет filtered/rejected."""
    t = settings.relevance_threshold if threshold is None else threshold
    records = session.scalars(
        select(ArticleRecord).where(ArticleRecord.status == ArticleStatus.new)
    ).all()

    filtered = 0
    rejected = 0
    for rec in records:
        art = Article(
            title=rec.title,
            url=rec.url,
            text=rec.text,
            source=rec.source,
            published_at=rec.published_at,
        )
        res = score_relevance(art, client=client)
        rec.relevance_score = res.score
        rec.relevance_reason = res.reason
        if res.score >= t:
            rec.status = ArticleStatus.filtered
            filtered += 1
        else:
            rec.status = ArticleStatus.rejected
            rejected += 1

    session.flush()
    return FilterResult(filtered=filtered, rejected=rejected)
