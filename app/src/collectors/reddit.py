"""Сборщик постов с Reddit через публичный JSON (.json у любой страницы)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone

import httpx

from src.collectors.base import Article

USER_AGENT = "article-pipeline/0.1 (Telegram channel for beginner programmers)"


def listing_url(subreddit: str, *, period: str = "week", limit: int = 10) -> str:
    return f"https://www.reddit.com/r/{subreddit}/top.json?t={period}&limit={limit}"


def _fetch_json(url: str) -> dict:
    resp = httpx.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True
    )
    resp.raise_for_status()
    return resp.json()


def collect_reddit(
    subreddits: Iterable[str],
    *,
    period: str = "week",
    limit: int = 10,
    fetcher: Callable[[str], dict] = _fetch_json,
) -> list[Article]:
    """subreddits — имена сабреддитов без r/. fetcher подменяется в тестах."""
    articles: list[Article] = []
    for sub in (s.strip() for s in subreddits if s.strip()):
        data = fetcher(listing_url(sub, period=period, limit=limit))
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            title = (d.get("title") or "").strip()
            permalink = d.get("permalink") or ""
            url = f"https://www.reddit.com{permalink}" if permalink else d.get("url", "")
            if not url:
                continue
            created = d.get("created_utc")
            published = (
                datetime.fromtimestamp(created, tz=timezone.utc) if created else None
            )
            text = (d.get("selftext") or "").strip()
            articles.append(
                Article(
                    title=title,
                    url=url,
                    text=text or title,
                    source=f"Reddit r/{sub}",
                    published_at=published,
                )
            )
    return articles
