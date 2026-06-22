"""Сборщик статей из arXiv через его Atom-API (парсим feedparser'ом)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone

import feedparser

from src.collectors.base import Article

API = "http://export.arxiv.org/api/query"


def build_query_url(categories: Iterable[str], *, max_results: int = 10) -> str:
    cats = [c.strip() for c in categories if c.strip()]
    search = "+OR+".join(f"cat:{c}" for c in cats) or "cat:cs.SE"
    return (
        f"{API}?search_query={search}"
        f"&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    )


def _published(entry) -> datetime | None:
    value = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime(*value[:6], tzinfo=timezone.utc) if value else None


def collect_arxiv(
    categories: Iterable[str],
    *,
    max_results: int = 10,
    fetcher: Callable[[str], str] | None = None,
) -> list[Article]:
    """categories — коды arXiv (cs.SE, cs.PL, ...). fetcher подменяется в тестах."""
    cats = [c.strip() for c in categories if c.strip()]
    if not cats:
        return []
    url = build_query_url(cats, max_results=max_results)
    # feedparser.parse принимает и URL (сам скачает), и готовый XML-текст
    parsed = feedparser.parse(fetcher(url) if fetcher else url)
    articles: list[Article] = []
    for entry in parsed.entries:
        link = entry.get("link")
        if not link:
            continue
        articles.append(
            Article(
                title=" ".join(entry.get("title", "").split()),
                url=link,
                text=(entry.get("summary") or "").strip(),
                source="arXiv",
                published_at=_published(entry),
            )
        )
    return articles
