"""Логика модерации: переходы статусов черновиков и разбор callback'ов."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import ArticleRecord, ArticleStatus

CALLBACK_PREFIX = "mod"
ACTIONS = {"approve", "edit", "reject"}


def build_callback(action: str, article_id: int) -> str:
    return f"{CALLBACK_PREFIX}:{action}:{article_id}"


def parse_callback(data: str) -> tuple[str, int] | None:
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != CALLBACK_PREFIX:
        return None
    action, raw_id = parts[1], parts[2]
    if action not in ACTIONS or not raw_id.isdigit():
        return None
    return action, int(raw_id)


def get_drafts(
    session: Session, *, limit: int | None = None
) -> Sequence[ArticleRecord]:
    stmt = select(ArticleRecord).where(ArticleRecord.status == ArticleStatus.drafted)
    if limit:
        stmt = stmt.limit(limit)
    return session.scalars(stmt).all()


def get_post_text(session: Session, article_id: int) -> str | None:
    rec = session.get(ArticleRecord, article_id)
    return rec.post_text if rec else None


def get_image(session: Session, article_id: int) -> str | None:
    rec = session.get(ArticleRecord, article_id)
    return rec.image_url if rec else None


def mark_pending(session: Session, article_id: int) -> None:
    rec = session.get(ArticleRecord, article_id)
    if rec and rec.status == ArticleStatus.drafted:
        rec.status = ArticleStatus.pending
        session.flush()


def set_post_text(session: Session, article_id: int, text: str) -> None:
    rec = session.get(ArticleRecord, article_id)
    if rec:
        rec.post_text = text
        session.flush()


def reject(session: Session, article_id: int) -> None:
    rec = session.get(ArticleRecord, article_id)
    if rec:
        rec.status = ArticleStatus.rejected
        session.flush()


def mark_published(
    session: Session, article_id: int, message_id: int | None = None
) -> None:
    rec = session.get(ArticleRecord, article_id)
    if rec:
        rec.tg_message_id = message_id
        rec.status = ArticleStatus.published
        session.flush()
