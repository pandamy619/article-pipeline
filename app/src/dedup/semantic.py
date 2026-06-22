"""Семантический дедуп статей по эмбеддингам (bge-m3 через Ollama).

Ловит почти-дубли (одна новость в разных источниках, рерайт), которые
не отлавливаются точным дедупом по URL/хешу.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.db.models import ArticleRecord, ArticleStatus


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


@dataclass(slots=True)
class DedupResult:
    checked: int
    duplicates: int


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _embed_input(rec: ArticleRecord) -> str:
    return f"{rec.title}\n\n{rec.text}".strip()


def _load_refs(
    session: Session, window: int, channel_id: int | None = None
) -> list[tuple[str, list[float]]]:
    """Эталоны: ранее принятые (не rejected) статьи с эмбеддингом."""
    stmt = select(ArticleRecord).where(
        ArticleRecord.embedding.is_not(None),
        ArticleRecord.status != ArticleStatus.rejected,
    )
    if channel_id is not None:
        stmt = stmt.where(ArticleRecord.channel_id == channel_id)
    rows = session.scalars(
        stmt.order_by(ArticleRecord.id.desc()).limit(window)
    ).all()
    refs: list[tuple[str, list[float]]] = []
    for r in rows:
        try:
            refs.append((r.title, json.loads(r.embedding)))
        except (TypeError, ValueError):
            continue
    return refs


def apply_semantic_dedup(
    session: Session,
    client: Embedder,
    *,
    threshold: float | None = None,
    window: int | None = None,
    channel_id: int | None = None,
) -> DedupResult:
    """Новые статьи сравниваем с ранее принятыми по косинусной близости.

    Похожие (>= threshold) → rejected; уникальным сохраняем эмбеддинг.
    Если эмбеддинг не получить (нет модели/сети) — статью пропускаем без
    падения прогона.
    """
    thr = settings.semantic_dedup_threshold if threshold is None else threshold
    win = settings.semantic_dedup_window if window is None else window

    refs = _load_refs(session, win, channel_id)
    nr_stmt = select(ArticleRecord).where(ArticleRecord.status == ArticleStatus.new)
    if channel_id is not None:
        nr_stmt = nr_stmt.where(ArticleRecord.channel_id == channel_id)
    new_records = session.scalars(nr_stmt).all()

    checked = 0
    duplicates = 0
    for rec in new_records:
        try:
            emb = client.embed(_embed_input(rec))
        except Exception:  # noqa: BLE001 — нет эмбеддинга → дедуп пропускаем
            continue
        if not emb:
            continue
        checked += 1

        best_title, best_sim = "", 0.0
        for title, ref in refs:
            sim = cosine(emb, ref)
            if sim > best_sim:
                best_sim, best_title = sim, title

        if best_sim >= thr:
            rec.status = ArticleStatus.rejected
            rec.relevance_reason = (
                f"семантический дубликат (похоже на: {best_title[:80]})"
            )
            duplicates += 1
        else:
            rec.embedding = json.dumps(emb)
            refs.append((rec.title, emb))

    session.flush()
    return DedupResult(checked=checked, duplicates=duplicates)
