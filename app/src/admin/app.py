"""JSON-API админки. Фронт — отдельный React/TS клиент (web/)."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, select

from src.config import settings
from src.db.base import get_session
from src.db.models import ArticleRecord, ArticleStatus
from src.feeds import service as feeds_service
from src.log import setup_logging

setup_logging()

app = FastAPI(title="article-pipeline admin API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ArticleOut(BaseModel):
    id: int
    status: str
    relevance_score: int | None
    relevance_reason: str | None
    title: str
    url: str
    source: str
    has_post: bool
    post_text: str | None
    image_url: str | None


def _to_out(rec: ArticleRecord) -> ArticleOut:
    return ArticleOut(
        id=rec.id,
        status=rec.status.value,
        relevance_score=rec.relevance_score,
        relevance_reason=rec.relevance_reason,
        title=rec.title,
        url=rec.url,
        source=rec.source,
        has_post=bool(rec.post_text),
        post_text=rec.post_text,
        image_url=rec.image_url,
    )


@app.get("/api/stats")
def stats() -> dict[str, int]:
    with get_session() as session:
        rows = session.execute(
            select(ArticleRecord.status, func.count()).group_by(ArticleRecord.status)
        ).all()
    counts = {s.value: 0 for s in ArticleStatus}
    for st, n in rows:
        counts[st.value] = n
    counts["total"] = sum(counts.values())
    return counts


@app.get("/api/articles")
def list_articles(status: str | None = None, limit: int = 200) -> list[ArticleOut]:
    with get_session() as session:
        stmt = select(ArticleRecord).order_by(ArticleRecord.id.desc()).limit(limit)
        if status:
            stmt = stmt.where(ArticleRecord.status == ArticleStatus(status))
        return [_to_out(r) for r in session.scalars(stmt).all()]


@app.post("/api/articles/{article_id}/reject")
def reject_article(article_id: int) -> dict[str, bool]:
    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        if rec:
            rec.status = ArticleStatus.rejected
    return {"ok": True}


class StatusIn(BaseModel):
    status: str


@app.post("/api/articles/{article_id}/status")
def set_status(article_id: int, body: StatusIn) -> dict[str, bool]:
    try:
        new_status = ArticleStatus(body.status)
    except ValueError:
        return {"ok": False}
    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        if rec is None:
            return {"ok": False}
        if rec.status == ArticleStatus.published:
            return {"ok": False}  # опубликованную статью менять нельзя
        rec.status = new_status
    return {"ok": True}


@app.post("/api/articles/{article_id}/draft")
async def draft_article(article_id: int) -> dict[str, bool]:
    def _make() -> None:
        from src.collectors.base import Article
        from src.llm.client import OllamaClient
        from src.rewrite.post import generate_post

        with get_session() as session:
            rec = session.get(ArticleRecord, article_id)
            if not rec:
                return
            art = Article(rec.title, rec.url, rec.text, rec.source, rec.published_at)
            rec.post_text = generate_post(art, client=OllamaClient())
            rec.status = ArticleStatus.drafted

    await asyncio.to_thread(_make)
    return {"ok": True}


@app.post("/api/articles/{article_id}/publish")
async def publish_article(article_id: int) -> dict[str, bool]:
    from aiogram import Bot

    from src.publisher.telegram import publish

    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        post = rec.post_text if rec else None
        image = rec.image_url if rec else None
    if not post:
        return {"ok": False}

    bot = Bot(settings.telegram_bot_token)
    try:
        message_id = await publish(
            bot, settings.telegram_channel_id, post, image_url=image
        )
    finally:
        await bot.session.close()

    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        if rec:
            rec.tg_message_id = message_id
            rec.status = ArticleStatus.published
    return {"ok": True}


class PostUpdate(BaseModel):
    text: str


class ReviseIn(BaseModel):
    instruction: str


SOURCE_SEP = "\n\nИсточник:"


@app.post("/api/articles/{article_id}/post")
def save_post(article_id: int, body: PostUpdate) -> dict[str, bool]:
    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        if rec:
            rec.post_text = body.text
    return {"ok": True}


@app.post("/api/articles/{article_id}/revise")
async def revise(article_id: int, body: ReviseIn) -> dict[str, object]:
    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        current = (rec.post_text or "") if rec else ""
        url = rec.url if rec else ""
    if not current:
        return {"ok": False}

    body_only = current.split(SOURCE_SEP)[0]

    def _revise() -> str:
        from src.llm.client import OllamaClient
        from src.rewrite.post import _assemble, revise_post

        new_body = revise_post(body_only, body.instruction, client=OllamaClient())
        return _assemble(new_body, url)

    new_post = await asyncio.to_thread(_revise)
    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        if rec:
            rec.post_text = new_post
    return {"ok": True, "post": new_post}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    messages: list[ChatMessage]


def _chat_system(title: str, text: str, post: str) -> str:
    return (
        "Ты — помощник редактора Telegram-канала для начинающих программистов. "
        "Обсуждай статью и помогай улучшить пост. Отвечай кратко, по-русски. "
        "Если просят переписать пост — пришли только готовый текст поста.\n\n"
        f"Статья:\nЗаголовок: {title}\nТекст: {text[:2000]}\n\n"
        f"Текущий пост:\n{post}"
    )


@app.post("/api/articles/{article_id}/chat")
async def chat(article_id: int, body: ChatIn) -> dict[str, str]:
    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        if not rec:
            return {"reply": ""}
        system = _chat_system(rec.title, rec.text, rec.post_text or "")

    msgs = [{"role": "system", "content": system}]
    msgs += [{"role": m.role, "content": m.content} for m in body.messages]

    def _chat() -> str:
        from src.llm.client import OllamaClient

        return OllamaClient().chat(msgs)

    reply = await asyncio.to_thread(_chat)
    return {"reply": reply}


class FeedOut(BaseModel):
    id: int | None
    url: str
    enabled: bool
    source: str  # "env" (из .env, не удаляется) или "db" (управляется тут)


class FeedIn(BaseModel):
    url: str


@app.get("/api/feeds")
def list_feeds_api() -> list[FeedOut]:
    with get_session() as session:
        env = [
            FeedOut(id=None, url=u, enabled=True, source="env")
            for u in settings.rss_feed_list
        ]
        db = [
            FeedOut(id=f.id, url=f.url, enabled=f.enabled, source="db")
            for f in feeds_service.list_feeds(session)
        ]
    return env + db


@app.post("/api/feeds")
def add_feed_api(body: FeedIn) -> dict[str, object]:
    with get_session() as session:
        feed = feeds_service.add_feed(session, body.url)
        return {"ok": bool(feed), "id": feed.id if feed else None}


@app.delete("/api/feeds/{feed_id}")
def delete_feed_api(feed_id: int) -> dict[str, bool]:
    with get_session() as session:
        ok = feeds_service.remove_feed(session, feed_id)
    return {"ok": ok}


@app.post("/api/collect")
async def collect_now() -> dict[str, bool]:
    def _run() -> None:
        from src.llm.client import OllamaClient
        from src.pipeline import run_pipeline

        with get_session() as session:
            run_pipeline(session, OllamaClient())

    await asyncio.to_thread(_run)
    return {"ok": True}
