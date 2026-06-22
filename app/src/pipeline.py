"""Оркестрация одного прогона: сбор -> сохранение -> фильтр -> рерайт."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.collectors.base import Article
from src.collectors.sources import collect_all
from src.config import settings
from src.db.repo import save_articles
from src.dedup.semantic import DedupResult, apply_semantic_dedup
from src.filter.relevance import Scorer
from src.filter.service import apply_relevance_filter
from src.rewrite.service import apply_rewrite


@dataclass(slots=True)
class PipelineResult:
    collected: int
    added: int
    duplicates: int
    semantic_duplicates: int
    filtered: int
    rejected: int
    drafted: int


def _default_collector(feeds: Iterable[str]) -> list[Article]:
    return collect_all(feeds)


def run_pipeline(
    session: Session,
    llm_client: Scorer,
    *,
    collector: Callable[[Iterable[str]], list[Article]] = _default_collector,
    feeds: list[str] | None = None,
) -> PipelineResult:
    """Один полный прогон: RSS -> дедуп -> фильтр релевантности -> рерайт в черновики."""
    feeds = feeds if feeds is not None else settings.rss_feed_list
    articles = list(collector(feeds))
    if settings.max_articles_per_run:
        articles = articles[: settings.max_articles_per_run]
    saved = save_articles(session, articles)
    if settings.semantic_dedup_enabled:
        deduped = apply_semantic_dedup(session, llm_client)
    else:
        deduped = DedupResult(checked=0, duplicates=0)
    filtered = apply_relevance_filter(session, llm_client)
    rewritten = apply_rewrite(session, llm_client)
    return PipelineResult(
        collected=len(articles),
        added=saved.added,
        duplicates=saved.duplicates,
        semantic_duplicates=deduped.duplicates,
        filtered=filtered.filtered,
        rejected=filtered.rejected,
        drafted=rewritten.drafted,
    )
