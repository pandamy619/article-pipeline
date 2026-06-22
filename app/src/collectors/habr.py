"""Сборщик статей с Habr через его RSS-ленты."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from src.collectors.base import Article
from src.collectors.rss import collect_rss, fetch_article_text

GENERAL_FEED = "https://habr.com/ru/rss/articles/?fl=ru"
HUB_FEED = "https://habr.com/ru/rss/hubs/{hub}/articles/?fl=ru"


def habr_feeds(hubs: Iterable[str]) -> list[str]:
    """URL'ы лент: по хабам, либо одна общая лента (RU), если хабы не заданы."""
    aliases = [h.strip() for h in hubs if h.strip()]
    if not aliases:
        return [GENERAL_FEED]
    return [HUB_FEED.format(hub=a) for a in aliases]


def collect_habr(
    hubs: Iterable[str] = (),
    *,
    limit_per_hub: int | None = None,
    text_fetcher: Callable[[str], str | None] = fetch_article_text,
) -> list[Article]:
    articles = collect_rss(
        habr_feeds(hubs), limit_per_feed=limit_per_hub, text_fetcher=text_fetcher
    )
    for art in articles:
        art.source = "Habr"
    return articles
