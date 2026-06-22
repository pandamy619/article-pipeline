"""Сборщик статей через веб-поиск (self-hosted SearXNG, JSON-API)."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import httpx

from src.collectors.base import Article
from src.collectors.rss import fetch_article_text
from src.config import settings


def _search(
    query: str, *, base_url: str, language: str, max_results: int
) -> list[dict]:
    resp = httpx.get(
        f"{base_url.rstrip('/')}/search",
        params={"q": query, "format": "json", "language": language, "safesearch": 0},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])[:max_results]


def collect_websearch(
    queries: Iterable[str],
    *,
    base_url: str | None = None,
    language: str = "ru",
    max_results: int = 10,
    searcher: Callable[[str], list[dict]] | None = None,
    text_fetcher: Callable[[str], str | None] = fetch_article_text,
) -> list[Article]:
    """По каждому запросу берём выдачу SearXNG и нормализуем в Article.

    searcher/text_fetcher подменяются в тестах (офлайн).
    """
    qs = [q.strip() for q in queries if q.strip()]
    if not qs:
        return []
    base = base_url or settings.searxng_url
    if searcher is None and not base:
        return []

    def _do(q: str) -> list[dict]:
        if searcher:
            return searcher(q)
        return _search(q, base_url=base, language=language, max_results=max_results)

    seen: set[str] = set()
    articles: list[Article] = []
    for q in qs:
        for r in _do(q):
            url = r.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            snippet = (r.get("content") or "").strip()
            text = text_fetcher(url) or snippet
            articles.append(
                Article(
                    title=(r.get("title") or "").strip(),
                    url=url,
                    text=(text or "").strip(),
                    source="Веб-поиск",
                    published_at=None,
                    image_url=(r.get("img_src") or None),
                )
            )
    return articles
