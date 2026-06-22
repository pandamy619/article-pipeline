"""Сборщик статей из RSS-лент."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Callable, Iterable

import feedparser

from src.collectors.base import Article


def fetch_article_text(url: str) -> str | None:
    """Достаёт основной текст статьи по ссылке (ленивый импорт trafilatura)."""
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    return trafilatura.extract(downloaded, include_comments=False, include_tables=False)


def _parsed_datetime(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime(*value[:6], tzinfo=timezone.utc)
    return None


def _entry_image(entry) -> str | None:
    """Картинка из RSS-записи: media:thumbnail/content или enclosure-image."""
    for key in ("media_thumbnail", "media_content"):
        media = entry.get(key)
        if media:
            url = media[0].get("url")
            if url:
                return url
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and link.get("type", "").startswith("image"):
            return link.get("href")
    return None


def collect_rss(
    feeds: Iterable[str],
    *,
    text_fetcher: Callable[[str], str | None] = fetch_article_text,
    limit_per_feed: int | None = None,
) -> list[Article]:
    """Парсит RSS-ленты и возвращает нормализованные статьи.

    feeds — список URL (или сырой XML, удобно для тестов).
    text_fetcher — как доставать полный текст (можно подменить в тестах).
    """
    articles: list[Article] = []
    for feed in feeds:
        parsed = feedparser.parse(feed)
        source = parsed.feed.get("title") or feed
        entries = parsed.entries[:limit_per_feed] if limit_per_feed else parsed.entries
        for entry in entries:
            link = entry.get("link")
            if not link:
                continue
            text = text_fetcher(link) or entry.get("summary", "")
            articles.append(
                Article(
                    title=entry.get("title", "").strip(),
                    url=link,
                    text=(text or "").strip(),
                    source=source,
                    published_at=_parsed_datetime(entry),
                    image_url=_entry_image(entry),
                )
            )
    return articles


def _demo() -> None:
    from src.config import settings

    feeds = sys.argv[1:] or settings.rss_feed_list
    if not feeds:
        print("Передай URL ленты аргументом или задай RSS_FEEDS в .env")
        return
    for art in collect_rss(feeds, limit_per_feed=5):
        print(
            f"- {art.title}\n  {art.url}\n  {art.source} | {art.published_at} | {len(art.text)} симв.\n"
        )


if __name__ == "__main__":
    _demo()
