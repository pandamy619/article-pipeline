"""Оркестрация прогона на канал: сбор -> дедуп -> фильтр -> рерайт."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.channels.service import ensure_default_channel, list_channels
from src.collectors.base import Article
from src.collectors.sources import collect_for_channel
from src.config import settings
from src.db.models import Channel, RunLog
from src.db.repo import save_articles
from src.dedup.semantic import DedupResult, apply_semantic_dedup
from src.filter.relevance import Scorer
from src.filter.service import apply_relevance_filter
from src.rewrite.service import apply_rewrite


@dataclass(slots=True)
class PipelineResult:
    collected: int
    added: int
    duplicates: int
    semantic_duplicates: int
    filtered: int
    rejected: int
    drafted: int


def run_pipeline(
    session: Session,
    llm_client: Scorer,
    channel: Channel,
    *,
    collector: Callable[[Channel], list[Article]] | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> PipelineResult:
    """Полный прогон одного канала: сбор -> дедуп -> фильтр -> рерайт в черновики."""

    def _p(stage: str, done: int = 0, total: int = 0) -> None:
        if on_progress:
            on_progress(stage, done, total)

    _p("collect")
    if collector is None:
        articles = collect_for_channel(channel)
    else:
        articles = list(collector(channel))
    if settings.max_articles_per_run:
        articles = articles[: settings.max_articles_per_run]

    saved = save_articles(session, articles, channel_id=channel.id)
    if settings.semantic_dedup_enabled:
        _p("dedup")
        deduped = apply_semantic_dedup(session, llm_client, channel_id=channel.id)
    else:
        deduped = DedupResult(checked=0, duplicates=0)
    filtered = apply_relevance_filter(
        session,
        llm_client,
        topic=channel.topic,
        threshold=channel.relevance_threshold,
        channel_id=channel.id,
        on_progress=lambda d, t: _p("filter", d, t),
    )
    rewritten = apply_rewrite(
        session,
        llm_client,
        channel_id=channel.id,
        on_progress=lambda d, t: _p("rewrite", d, t),
    )
    _p("done")

    result = PipelineResult(
        collected=len(articles),
        added=saved.added,
        duplicates=saved.duplicates,
        semantic_duplicates=deduped.duplicates,
        filtered=filtered.filtered,
        rejected=filtered.rejected,
        drafted=rewritten.drafted,
    )
    session.add(
        RunLog(
            collected=result.collected,
            added=result.added,
            duplicates=result.duplicates,
            semantic_duplicates=result.semantic_duplicates,
            filtered=result.filtered,
            rejected=result.rejected,
            drafted=result.drafted,
            ok=True,
        )
    )
    session.flush()
    return result


def run_all_channels(
    session: Session,
    llm_client: Scorer,
    *,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> PipelineResult:
    """Прогоняет все включённые каналы, возвращает суммарный результат."""
    ensure_default_channel(session)
    total = PipelineResult(0, 0, 0, 0, 0, 0, 0)
    for channel in list_channels(session):
        if not channel.enabled:
            continue
        r = run_pipeline(session, llm_client, channel, on_progress=on_progress)
        total = PipelineResult(
            collected=total.collected + r.collected,
            added=total.added + r.added,
            duplicates=total.duplicates + r.duplicates,
            semantic_duplicates=total.semantic_duplicates + r.semantic_duplicates,
            filtered=total.filtered + r.filtered,
            rejected=total.rejected + r.rejected,
            drafted=total.drafted + r.drafted,
        )
    return total
