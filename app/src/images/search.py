"""Поиск картинок: бесплатные стоки (Pexels/Pixabay) + SearXNG (категория images).

Возвращаем кандидатов (превью + полноразмер); скачивание выбранной — отдельно
(media.fetch), уже при сохранении поста.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from src.config import settings


@dataclass(slots=True)
class ImageHit:
    url: str  # полноразмерная картинка
    thumb: str  # превью (для галереи)
    source: str  # pexels | pixabay | web
    title: str = ""


def _get_json(url: str, *, params: dict, headers: dict | None = None) -> dict:
    resp = httpx.get(url, params=params, headers=headers or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _pexels(query: str, limit: int, fetcher: Callable[[str], dict] | None) -> list[ImageHit]:
    if not settings.pexels_api_key:
        return []
    data = (
        fetcher(query)
        if fetcher
        else _get_json(
            "https://api.pexels.com/v1/search",
            params={"query": query, "per_page": limit},
            headers={"Authorization": settings.pexels_api_key},
        )
    )
    hits: list[ImageHit] = []
    for p in data.get("photos", [])[:limit]:
        src = p.get("src") or {}
        url = src.get("large2x") or src.get("large") or src.get("original")
        if url:
            hits.append(
                ImageHit(
                    url=url,
                    thumb=src.get("medium") or src.get("small") or url,
                    source="pexels",
                    title=(p.get("alt") or "").strip(),
                )
            )
    return hits


def _pixabay(query: str, limit: int, fetcher: Callable[[str], dict] | None) -> list[ImageHit]:
    if not settings.pixabay_api_key:
        return []
    data = (
        fetcher(query)
        if fetcher
        else _get_json(
            "https://pixabay.com/api/",
            params={
                "key": settings.pixabay_api_key,
                "q": query,
                "per_page": max(3, limit),
                "image_type": "photo",
                "safesearch": "true",
            },
        )
    )
    hits: list[ImageHit] = []
    for p in data.get("hits", [])[:limit]:
        url = p.get("largeImageURL") or p.get("webformatURL")
        if url:
            hits.append(
                ImageHit(
                    url=url,
                    thumb=p.get("webformatURL") or p.get("previewURL") or url,
                    source="pixabay",
                    title=(p.get("tags") or "").strip(),
                )
            )
    return hits


def _searx(query: str, limit: int, fetcher: Callable[[str], dict] | None) -> list[ImageHit]:
    if not fetcher and not settings.searxng_url:
        return []
    data = (
        fetcher(query)
        if fetcher
        else _get_json(
            f"{settings.searxng_url.rstrip('/')}/search",
            params={
                "q": query,
                "format": "json",
                "categories": "images",
                "safesearch": 1,
            },
        )
    )
    hits: list[ImageHit] = []
    for r in data.get("results", [])[:limit]:
        url = r.get("img_src")
        if url:
            hits.append(
                ImageHit(
                    url=url,
                    thumb=r.get("thumbnail_src") or url,
                    source="web",
                    title=(r.get("title") or "").strip(),
                )
            )
    return hits


def image_keywords(client, text: str) -> str:
    """По тексту поста LLM придумывает короткий запрос для поиска иллюстрации."""
    text = (text or "").strip()
    if not text:
        return ""
    system = (
        "Ты подбираешь иллюстрацию к посту. По тексту придумай ОДИН короткий "
        "поисковый запрос для фотостока: 2–4 слова, без хэштегов, кавычек и "
        "пунктуации. Можно по-английски, если так найдётся лучше. Ответь ТОЛЬКО "
        "запросом, без пояснений."
    )
    try:
        raw = client.generate(text[:2000], system=system)
    except Exception:  # noqa: BLE001 — нет LLM -> пустой запрос
        return ""
    line = (raw or "").strip().splitlines()[0] if raw else ""
    return line.strip().strip('"').strip()[:80]


def search_images(
    query: str,
    *,
    source: str = "stock",
    limit: int = 12,
    pexels: Callable[[str], dict] | None = None,
    pixabay: Callable[[str], dict] | None = None,
    searx: Callable[[str], dict] | None = None,
) -> list[ImageHit]:
    """source=stock -> Pexels+Pixabay (что настроено); source=web -> SearXNG.

    *_fetcher подменяются в тестах (офлайн).
    """
    query = (query or "").strip()
    if not query:
        return []
    if source == "web":
        return _searx(query, limit, searx)
    hits = _pexels(query, limit, pexels) + _pixabay(query, limit, pixabay)
    return hits[:limit]
