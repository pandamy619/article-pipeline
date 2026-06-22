"""LLM-поиск статей: семантический по собранным + добыча новых из веба."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.channels.service import ensure_default_channel, get_channel
from src.collectors.websearch import collect_websearch
from src.db.models import ArticleRecord
from src.db.repo import save_articles
from src.dedup.semantic import cosine
from src.filter.service import apply_relevance_filter
from src.rewrite.service import apply_rewrite


def semantic_search(
    session: Session,
    client,
    query: str,
    *,
    channel_id: int | None = None,
    top: int = 20,
) -> list[tuple[ArticleRecord, float]]:
    """Эмбеддинг запроса -> косинус по статьям с эмбеддингом, ранжирование."""
    try:
        emb = client.embed(query)
    except Exception:  # noqa: BLE001 — нет эмбеддера -> пустой результат
        return []
    if not emb:
        return []
    stmt = select(ArticleRecord).where(ArticleRecord.embedding.is_not(None))
    if channel_id is not None:
        stmt = stmt.where(ArticleRecord.channel_id == channel_id)
    scored: list[tuple[ArticleRecord, float]] = []
    for rec in session.scalars(stmt).all():
        try:
            vec = json.loads(rec.embedding)
        except (TypeError, ValueError):
            continue
        scored.append((rec, cosine(emb, vec)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top]


def _parse_list(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [])
    if isinstance(data, list):
        return [str(x).strip() for x in data if str(x).strip()]
    return []


def generate_queries(client, description: str, *, n: int = 4) -> list[str]:
    """LLM придумывает поисковые запросы по описанию темы."""
    system = (
        "Ты помогаешь искать статьи в интернете. По описанию темы придумай "
        "короткие поисковые запросы (можно по-русски и по-английски). "
        'Ответь СТРОГО JSON-массивом строк, например ["запрос один", "query two"].'
    )
    raw = client.generate(f"Описание: {description}", system=system, format="json")
    queries = _parse_list(raw)
    return queries[:n] if queries else [description]


def web_search_collect(
    session: Session, client, description: str, *, channel_id: int | None = None
) -> tuple[int, list[str]]:
    """По описанию: LLM-запросы -> SearXNG -> сохранить и прогнать фильтр+рерайт."""
    if channel_id is None:
        channel_id = ensure_default_channel(session).id
    queries = generate_queries(client, description)
    articles = collect_websearch(queries)
    saved = save_articles(session, articles, channel_id=channel_id)
    ch = get_channel(session, channel_id)
    apply_relevance_filter(
        session,
        client,
        topic=ch.topic if ch else None,
        threshold=ch.relevance_threshold if ch else None,
        channel_id=channel_id,
    )
    apply_rewrite(session, client, channel_id=channel_id)
    return saved.added, queries
