"""Агрегатор источников: собирает материалы из всех включённых коллекторов.

Каждый источник изолирован: падение одного (сеть, формат) не роняет прогон.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable

from src.collectors.arxiv import collect_arxiv
from src.collectors.base import Article
from src.collectors.habr import collect_habr
from src.collectors.reddit import collect_reddit
from src.collectors.rss import collect_rss
from src.config import settings


def collect_all(feeds: Iterable[str] | None = None) -> list[Article]:
    limit = settings.max_articles_per_run or None
    rss_feeds = list(feeds) if feeds is not None else settings.rss_feed_list
    articles: list[Article] = []

    def _safe(name: str, fn: Callable[[], list[Article]]) -> None:
        try:
            got = fn()
            articles.extend(got)
            print(f"[collect] {name}: {len(got)}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — один источник не должен ронять прогон
            print(f"[collect] {name} FAILED: {exc}", file=sys.stderr)

    if rss_feeds:
        _safe("rss", lambda: collect_rss(rss_feeds, limit_per_feed=limit))
    if settings.habr_enabled:
        _safe("habr", lambda: collect_habr(settings.habr_hub_list, limit_per_hub=limit))
    if settings.arxiv_category_list:
        _safe(
            "arxiv",
            lambda: collect_arxiv(
                settings.arxiv_category_list, max_results=settings.arxiv_max_results
            ),
        )
    if settings.reddit_subreddit_list:
        _safe(
            "reddit",
            lambda: collect_reddit(
                settings.reddit_subreddit_list,
                period=settings.reddit_period,
                limit=settings.reddit_limit,
            ),
        )
    return articles
