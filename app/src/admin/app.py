"""JSON-API админки. Фронт — отдельный React/TS клиент (web/)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, select

from src.channels import service as channels_service
from src.config import settings
from src.db.base import get_session
from src.db.models import (
    ArticleRecord,
    ArticleStatus,
    Channel,
    CollectJob,
    CollectJobStatus,
    RunLog,
)
from src.feeds import service as feeds_service
from src.log import setup_logging
from src.publisher.queue import parse_when, schedule_article, unschedule
from src.search.service import semantic_search
from src.settings_store import EDITABLE, apply_overrides, current_values, set_override

setup_logging()


def require_auth(authorization: str | None = Header(default=None)) -> None:
    """Защита админки токеном. Пустой ADMIN_TOKEN -> авторизация выключена."""
    token = settings.admin_token
    if not token:
        return
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="unauthorized")


def apply_runtime_settings() -> None:
    """Накатывает рантайм-настройки из БД на каждый запрос админки."""
    with get_session() as session:
        apply_overrides(session)


app = FastAPI(
    title="article-pipeline admin API",
    dependencies=[Depends(require_auth), Depends(apply_runtime_settings)],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/auth/check")
def auth_check() -> dict[str, bool]:
    return {"ok": True}


def _publish_target(session, channel_id: int | None) -> tuple[str, str]:
    """Бот-токен и chat_id для публикации статьи: канала или из .env (фолбэк)."""
    ch = channels_service.get_channel(session, channel_id) if channel_id else None
    token = ch.bot_token if ch and ch.bot_token else settings.telegram_bot_token
    chat = ch.channel_id if ch and ch.channel_id else settings.telegram_channel_id
    return token, chat


class ArticleOut(BaseModel):
    id: int
    channel_id: int | None
    status: str
    relevance_score: int | None
    relevance_reason: str | None
    title: str
    url: str
    source: str
    has_post: bool
    post_text: str | None
    image_url: str | None
    scheduled_at: str | None


def _to_out(rec: ArticleRecord) -> ArticleOut:
    return ArticleOut(
        id=rec.id,
        channel_id=rec.channel_id,
        status=rec.status.value,
        relevance_score=rec.relevance_score,
        relevance_reason=rec.relevance_reason,
        title=rec.title,
        url=rec.url,
        source=rec.source,
        has_post=bool(rec.post_text),
        post_text=rec.post_text,
        image_url=rec.image_url,
        scheduled_at=rec.scheduled_at.isoformat() if rec.scheduled_at else None,
    )


@app.get("/api/stats")
def stats(channel: int | None = None) -> dict[str, int]:
    with get_session() as session:
        stmt = select(ArticleRecord.status, func.count())
        if channel is not None:
            stmt = stmt.where(ArticleRecord.channel_id == channel)
        rows = session.execute(stmt.group_by(ArticleRecord.status)).all()
    counts = {s.value: 0 for s in ArticleStatus}
    for st, n in rows:
        counts[st.value] = n
    counts["total"] = sum(counts.values())
    return counts


@app.get("/api/articles")
def list_articles(
    status: str | None = None, channel: int | None = None, limit: int = 200
) -> list[ArticleOut]:
    with get_session() as session:
        stmt = select(ArticleRecord).order_by(ArticleRecord.id.desc())
        if status:
            stmt = stmt.where(ArticleRecord.status == ArticleStatus(status))
        if channel is not None:
            stmt = stmt.where(ArticleRecord.channel_id == channel)
        return [_to_out(r) for r in session.scalars(stmt.limit(limit)).all()]


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


class ScheduleIn(BaseModel):
    when: str | None = None


@app.post("/api/articles/{article_id}/schedule")
def schedule_article_api(article_id: int, body: ScheduleIn) -> dict[str, object]:
    with get_session() as session:
        when = schedule_article(session, article_id, parse_when(body.when))
        return {
            "ok": when is not None,
            "scheduled_at": when.isoformat() if when else None,
        }


@app.post("/api/articles/{article_id}/unschedule")
def unschedule_article_api(article_id: int) -> dict[str, bool]:
    with get_session() as session:
        return {"ok": unschedule(session, article_id)}


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
    from src.bot_factory import make_bot
    from src.publisher.telegram import publish

    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        post = rec.post_text if rec else None
        image = rec.image_url if rec else None
        token, chat = _publish_target(session, rec.channel_id if rec else None)
    if not post:
        return {"ok": False}

    bot = make_bot(token)
    try:
        message_id = await publish(bot, chat, post, image_url=image)
    finally:
        await bot.session.close()

    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        if rec:
            rec.tg_message_id = message_id
            rec.status = ArticleStatus.published
    return {"ok": True}


class BulkIn(BaseModel):
    ids: list[int]
    action: str  # reject | queue | unqueue | publish


@app.post("/api/articles/bulk")
async def bulk_action(body: BulkIn) -> dict[str, object]:
    if body.action in {"reject", "queue", "unqueue"}:
        done = 0
        with get_session() as session:
            for aid in body.ids:
                if body.action == "reject":
                    rec = session.get(ArticleRecord, aid)
                    if rec and rec.status != ArticleStatus.published:
                        rec.status = ArticleStatus.rejected
                        done += 1
                elif body.action == "queue":
                    if schedule_article(session, aid):
                        done += 1
                elif unschedule(session, aid):
                    done += 1
        return {"ok": True, "done": done}

    if body.action == "publish":
        from src.bot_factory import make_bot
        from src.publisher.telegram import publish

        done = 0
        for aid in body.ids:
            with get_session() as session:
                rec = session.get(ArticleRecord, aid)
                post = rec.post_text if rec else None
                image = rec.image_url if rec else None
                published = rec and rec.status == ArticleStatus.published
                token, chat = _publish_target(session, rec.channel_id if rec else None)
            if not post or published:
                continue
            bot = make_bot(token)
            try:
                mid = await publish(bot, chat, post, image_url=image)
            except Exception:  # noqa: BLE001 — одна не должна ронять пачку
                continue
            finally:
                await bot.session.close()
            with get_session() as session:
                rec = session.get(ArticleRecord, aid)
                if rec:
                    rec.tg_message_id = mid
                    rec.status = ArticleStatus.published
            done += 1
        return {"ok": True, "done": done}

    return {"ok": False, "done": 0}


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


class SettingIn(BaseModel):
    key: str
    value: str


@app.get("/api/settings")
def get_settings_api() -> dict[str, object]:
    with get_session() as session:
        return {"settings": current_values(session), "types": EDITABLE}


@app.post("/api/settings")
def set_setting_api(body: SettingIn) -> dict[str, bool]:
    with get_session() as session:
        return {"ok": set_override(session, body.key, body.value)}


@app.get("/api/last-run")
def last_run() -> dict[str, object]:
    with get_session() as session:
        rec = session.scalar(select(RunLog).order_by(RunLog.id.desc()))
        if not rec:
            return {"exists": False}
        return {
            "exists": True,
            "created_at": rec.created_at.isoformat(),
            "ok": rec.ok,
            "error": rec.error,
            "collected": rec.collected,
            "added": rec.added,
            "duplicates": rec.duplicates,
            "semantic_duplicates": rec.semantic_duplicates,
            "filtered": rec.filtered,
            "rejected": rec.rejected,
            "drafted": rec.drafted,
        }


class ChannelOut(BaseModel):
    id: int
    name: str
    bot_token: str
    channel_id: str
    admin_user_id: str
    topic: str
    enabled: bool
    relevance_threshold: int
    publish_interval_minutes: int
    collect_enabled: bool
    collect_interval_minutes: int
    next_collect_at: datetime | None
    rss_feeds: str
    habr_enabled: bool
    habr_hubs: str
    arxiv_categories: str
    reddit_subreddits: str
    searxng_queries: str


def _channel_out(ch: Channel) -> ChannelOut:
    return ChannelOut(
        id=ch.id,
        name=ch.name,
        bot_token=ch.bot_token,
        channel_id=ch.channel_id,
        admin_user_id=ch.admin_user_id,
        topic=ch.topic,
        enabled=ch.enabled,
        relevance_threshold=ch.relevance_threshold,
        publish_interval_minutes=ch.publish_interval_minutes,
        collect_enabled=ch.collect_enabled,
        collect_interval_minutes=ch.collect_interval_minutes,
        next_collect_at=ch.next_collect_at,
        rss_feeds=ch.rss_feeds,
        habr_enabled=ch.habr_enabled,
        habr_hubs=ch.habr_hubs,
        arxiv_categories=ch.arxiv_categories,
        reddit_subreddits=ch.reddit_subreddits,
        searxng_queries=ch.searxng_queries,
    )


class ChannelIn(BaseModel):
    name: str | None = None
    bot_token: str | None = None
    channel_id: str | None = None
    admin_user_id: str | None = None
    topic: str | None = None
    enabled: bool | None = None
    relevance_threshold: int | None = None
    publish_interval_minutes: int | None = None
    collect_enabled: bool | None = None
    collect_interval_minutes: int | None = None
    rss_feeds: str | None = None
    habr_enabled: bool | None = None
    habr_hubs: str | None = None
    arxiv_categories: str | None = None
    reddit_subreddits: str | None = None
    searxng_queries: str | None = None


@app.get("/api/channels")
def list_channels_api() -> list[ChannelOut]:
    with get_session() as session:
        channels_service.ensure_default_channel(session)
        return [_channel_out(c) for c in channels_service.list_channels(session)]


@app.post("/api/channels")
def create_channel_api(body: ChannelIn) -> ChannelOut:
    with get_session() as session:
        ch = channels_service.create_channel(
            session, **body.model_dump(exclude_unset=True)
        )
        return _channel_out(ch)


@app.put("/api/channels/{channel_id}")
def update_channel_api(channel_id: int, body: ChannelIn) -> ChannelOut:
    with get_session() as session:
        ch = channels_service.update_channel(
            session, channel_id, **body.model_dump(exclude_unset=True)
        )
        if not ch:
            raise HTTPException(status_code=404, detail="not found")
        return _channel_out(ch)


@app.delete("/api/channels/{channel_id}")
def delete_channel_api(channel_id: int) -> dict[str, bool]:
    with get_session() as session:
        return {"ok": channels_service.delete_channel(session, channel_id)}


class SearchIn(BaseModel):
    query: str
    mode: str = "semantic"  # semantic | web
    channel_id: int | None = None


@app.post("/api/search")
async def search_api(body: SearchIn) -> dict[str, object]:
    if body.mode == "web":
        # веб-поиск долгий (LLM+SearXNG+рерайт) — отдаём воркеру через очередь
        q = (body.query or "").strip()
        if not q:
            raise HTTPException(status_code=400, detail="empty query")
        chan_clause = (
            CollectJob.channel_id.is_(None)
            if body.channel_id is None
            else CollectJob.channel_id == body.channel_id
        )
        with get_session() as session:
            active = session.scalars(
                select(CollectJob)
                .where(
                    CollectJob.status.in_(
                        [CollectJobStatus.queued, CollectJobStatus.running]
                    ),
                    CollectJob.query == q,
                    chan_clause,
                )
                .order_by(CollectJob.created_at)
            ).first()
            if active:
                return {"mode": "web", "job": _job_out(active).model_dump(mode="json")}
            job = CollectJob(
                channel_id=body.channel_id, query=q, status=CollectJobStatus.queued
            )
            session.add(job)
            session.flush()
            return {"mode": "web", "job": _job_out(job).model_dump(mode="json")}

    def _sem() -> dict[str, object]:
        from src.llm.client import OllamaClient

        with get_session() as session:
            results = semantic_search(
                session, OllamaClient(), body.query, channel_id=body.channel_id
            )
            return {
                "mode": "semantic",
                "results": [
                    {
                        "id": r.id,
                        "title": r.title,
                        "url": r.url,
                        "status": r.status.value,
                        "channel_id": r.channel_id,
                        "similarity": round(sim, 3),
                    }
                    for r, sim in results
                ],
            }

    return await asyncio.to_thread(_sem)


class CollectJobOut(BaseModel):
    id: int
    channel_id: int | None
    query: str | None = None  # задан => веб-поиск
    status: str
    result: dict[str, object] | None = None  # сбор: счётчики; веб-поиск: added+queries
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


def _job_out(job: CollectJob) -> CollectJobOut:
    return CollectJobOut(
        id=job.id,
        channel_id=job.channel_id,
        query=job.query,
        status=job.status.value,
        result=json.loads(job.result) if job.result else None,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@app.post("/api/collect")
def collect_now(channel: int | None = None) -> CollectJobOut:
    """Ставит сбор в очередь; задачу разбирает бот-воркер (контейнер app)."""
    chan_clause = (
        CollectJob.channel_id.is_(None)
        if channel is None
        else CollectJob.channel_id == channel
    )
    with get_session() as session:
        # не плодим дубли: если по этому проекту уже есть активный сбор — вернём его
        # (query IS NULL — чтобы не путать с задачами веб-поиска)
        active = session.scalars(
            select(CollectJob)
            .where(
                CollectJob.status.in_(
                    [CollectJobStatus.queued, CollectJobStatus.running]
                ),
                CollectJob.query.is_(None),
                chan_clause,
            )
            .order_by(CollectJob.created_at)
        ).first()
        if active:
            return _job_out(active)
        job = CollectJob(channel_id=channel, status=CollectJobStatus.queued)
        session.add(job)
        session.flush()
        return _job_out(job)


@app.get("/api/collect/status/{job_id}")
def collect_status(job_id: int) -> CollectJobOut:
    with get_session() as session:
        job = session.get(CollectJob, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="not found")
        return _job_out(job)


@app.get("/api/collect/active")
def collect_active() -> list[CollectJobOut]:
    with get_session() as session:
        jobs = session.scalars(
            select(CollectJob)
            .where(
                CollectJob.status.in_(
                    [CollectJobStatus.queued, CollectJobStatus.running]
                )
            )
            .order_by(CollectJob.created_at)
        ).all()
        return [_job_out(j) for j in jobs]
