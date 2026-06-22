"""Сборщик статей из RSS-лент."""

from __future__ import annotations

import re
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


_OG_IMAGE_RE = re.compile(
    r"<meta[^>]+(?:property|name)=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_OG_IMAGE_RE_ALT = re.compile(
    r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+(?:property|name)=[\"']og:image[\"']",
    re.IGNORECASE,
)


def _og_image(html: str) -> str | None:
    for rx in (_OG_IMAGE_RE, _OG_IMAGE_RE_ALT):
        m = rx.search(html)
        if m:
            return m.group(1)
    return None


def fetch_article_meta(url: str) -> tuple[str | None, str | None]:
    """Скачивает страницу один раз: возвращает (текст, og:image)."""
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None, None
    text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    return text, _og_image(downloaded)


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
    text_fetcher: Callable[[str], str | None] | None = None,
    limit_per_feed: int | None = None,
) -> list[Article]:
    """Парсит RSS-ленты и возвращает нормализованные статьи.

    feeds — список URL (или сырой XML, удобно для тестов).
    text_fetcher — если задан, берём им только текст (для офлайн-тестов);
    иначе скачиваем страницу один раз и достаём текст + og:image.
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
            entry_img = _entry_image(entry)
            if text_fetcher is not None:
                text = text_fetcher(link) or entry.get("summary", "")
                image = entry_img
            else:
                text, page_img = fetch_article_meta(link)
                text = text or entry.get("summary", "")
                image = entry_img or page_img
            articles.append(
                Article(
                    title=entry.get("title", "").strip(),
                    url=link,
                    text=(text or "").strip(),
                    source=source,
                    published_at=_parsed_datetime(entry),
                    image_url=image,
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
