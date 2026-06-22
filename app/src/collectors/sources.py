"""Агрегатор источников: собирает материалы из всех включённых коллекторов.

Каждый источник изолирован: падение одного (сеть, формат) не роняет прогон.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from src.collectors.arxiv import collect_arxiv
from src.collectors.base import Article
from src.collectors.habr import collect_habr
from src.collectors.reddit import collect_reddit
from src.collectors.rss import collect_rss
from src.collectors.websearch import collect_websearch
from src.config import settings

log = logging.getLogger(__name__)


@dataclass(slots=True)
class SourceConfig:
    rss_feeds: list[str]
    habr_enabled: bool
    habr_hubs: list[str]
    arxiv_categories: list[str]
    reddit_subreddits: list[str]
    searxng_queries: list[str]


def _interleave(buckets: list[list[Article]]) -> list[Article]:
    """Round-robin: по одной статье из каждого источника по кругу."""
    out: list[Article] = []
    i = 0
    while True:
        added = False
        for bucket in buckets:
            if i < len(bucket):
                out.append(bucket[i])
                added = True
        if not added:
            break
        i += 1
    return out


def _collect(cfg: SourceConfig, limit: int | None) -> list[Article]:
    buckets: list[list[Article]] = []

    def _safe(name: str, fn: Callable[[], list[Article]]) -> None:
        try:
            got = fn()
            buckets.append(got)
            log.info("collect %s: %d", name, len(got))
        except Exception as exc:  # noqa: BLE001 — один источник не должен ронять прогон
            log.warning("collect %s failed: %s", name, exc)

    if cfg.rss_feeds:
        _safe("rss", lambda: collect_rss(cfg.rss_feeds, limit_per_feed=limit))
    if cfg.habr_enabled:
        _safe("habr", lambda: collect_habr(cfg.habr_hubs, limit_per_hub=limit))
    if cfg.arxiv_categories:
        _safe(
            "arxiv",
            lambda: collect_arxiv(
                cfg.arxiv_categories, max_results=settings.arxiv_max_results
            ),
        )
    if cfg.reddit_subreddits:
        _safe(
            "reddit",
            lambda: collect_reddit(
                cfg.reddit_subreddits,
                period=settings.reddit_period,
                limit=settings.reddit_limit,
            ),
        )
    if cfg.searxng_queries:
        _safe(
            "websearch",
            lambda: collect_websearch(
                cfg.searxng_queries,
                language=settings.searxng_language,
                max_results=settings.searxng_max_results,
            ),
        )
    return _interleave(buckets)


def collect_all(feeds: Iterable[str] | None = None) -> list[Article]:
    """Глобальный сбор по настройкам .env (для одноканального режима/тестов)."""
    cfg = SourceConfig(
        rss_feeds=list(feeds) if feeds is not None else settings.rss_feed_list,
        habr_enabled=settings.habr_enabled,
        habr_hubs=settings.habr_hub_list,
        arxiv_categories=settings.arxiv_category_list,
        reddit_subreddits=settings.reddit_subreddit_list,
        searxng_queries=settings.searxng_query_list,
    )
    return _collect(cfg, settings.max_articles_per_run or None)


def collect_for_channel(channel, *, limit: int | None = None) -> list[Article]:
    """Сбор по источникам конкретного канала."""
    from src.channels.service import split

    cfg = SourceConfig(
        rss_feeds=split(channel.rss_feeds),
        habr_enabled=channel.habr_enabled,
        habr_hubs=split(channel.habr_hubs),
        arxiv_categories=split(channel.arxiv_categories),
        reddit_subreddits=split(channel.reddit_subreddits),
        searxng_queries=split(channel.searxng_queries),
    )
    lim = limit if limit is not None else (settings.max_articles_per_run or None)
    return _collect(cfg, lim)
