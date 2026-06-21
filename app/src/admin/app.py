"""Веб-админка: просмотр собранных статей и ручные действия."""

from __future__ import annotations

import asyncio
import html

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from src.config import settings
from src.db.base import get_session
from src.db.models import ArticleRecord, ArticleStatus

app = FastAPI(title="article-pipeline admin")

_PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>article-pipeline</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:24px;color:#1a1a1a}}
 h1{{font-size:20px}}
 .filters a{{margin-right:10px;text-decoration:none;color:#2563eb}}
 table{{border-collapse:collapse;width:100%;margin-top:12px;font-size:14px}}
 td,th{{border:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}}
 th{{background:#f5f5f5}}
 small{{color:#666}}
 button{{cursor:pointer;margin:1px}}
 .st{{padding:2px 6px;border-radius:4px;font-size:12px}}
 .new{{background:#eee}} .filtered{{background:#dbeafe}} .drafted{{background:#fde68a}}
 .pending{{background:#fed7aa}} .published{{background:#bbf7d0}} .rejected{{background:#fecaca}}
</style></head><body>
<h1>article-pipeline — собранные статьи</h1>
<form method="post" action="/collect" style="margin-bottom:8px"><button>🔄 Собрать сейчас</button></form>
<div class="filters">{filters}</div>
<table>
<tr><th>id</th><th>статус</th><th>оценка</th><th>заголовок / причина</th><th>источник</th><th>действия</th></tr>
{rows}
</table></body></html>"""


def _row(rec: ArticleRecord) -> str:
    score = "" if rec.relevance_score is None else str(rec.relevance_score)
    reason = html.escape(rec.relevance_reason or "")
    title = html.escape(rec.title or "(без заголовка)")
    url = html.escape(rec.url)
    source = html.escape(rec.source or "")
    st = rec.status.value
    return (
        f"<tr><td>{rec.id}</td>"
        f'<td><span class="st {st}">{st}</span></td>'
        f"<td>{score}</td>"
        f'<td><a href="{url}" target="_blank">{title}</a><br><small>{reason}</small></td>'
        f"<td>{source}</td>"
        f"<td>"
        f'<form method="post" action="/articles/{rec.id}/draft" style="display:inline"><button title="сделать черновик">✍</button></form>'
        f'<form method="post" action="/articles/{rec.id}/publish" style="display:inline"><button title="опубликовать">✅</button></form>'
        f'<form method="post" action="/articles/{rec.id}/reject" style="display:inline"><button title="отклонить">❌</button></form>'
        f"</td></tr>"
    )


@app.get("/", response_class=HTMLResponse)
def index(status: str | None = None) -> str:
    with get_session() as session:
        counts = dict(
            session.execute(
                select(ArticleRecord.status, func.count()).group_by(
                    ArticleRecord.status
                )
            ).all()
        )
        stmt = select(ArticleRecord).order_by(ArticleRecord.id.desc()).limit(200)
        if status:
            stmt = stmt.where(ArticleRecord.status == ArticleStatus(status))
        rows = "".join(_row(r) for r in session.scalars(stmt).all())

    total = sum(counts.values())
    parts = [f'<a href="/">все ({total})</a>']
    parts += [
        f'<a href="/?status={s.value}">{s.value} ({counts.get(s, 0)})</a>'
        for s in ArticleStatus
    ]
    body = rows or '<tr><td colspan="6">пусто</td></tr>'
    return _PAGE.format(filters=" ".join(parts), rows=body)


@app.post("/articles/{article_id}/reject")
def reject_article(article_id: int) -> RedirectResponse:
    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        if rec:
            rec.status = ArticleStatus.rejected
    return RedirectResponse("/", status_code=303)


@app.post("/articles/{article_id}/draft")
async def draft_article(article_id: int) -> RedirectResponse:
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
    return RedirectResponse("/", status_code=303)


@app.post("/articles/{article_id}/publish")
async def publish_article(article_id: int) -> RedirectResponse:
    from aiogram import Bot

    from src.publisher.telegram import publish

    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        post = rec.post_text if rec else None
    if not post:
        return RedirectResponse("/", status_code=303)

    bot = Bot(settings.telegram_bot_token)
    try:
        message_id = await publish(bot, settings.telegram_channel_id, post)
    finally:
        await bot.session.close()

    with get_session() as session:
        rec = session.get(ArticleRecord, article_id)
        if rec:
            rec.tg_message_id = message_id
            rec.status = ArticleStatus.published
    return RedirectResponse("/", status_code=303)


@app.post("/collect")
async def collect_now() -> RedirectResponse:
    def _run() -> None:
        from src.llm.client import OllamaClient
        from src.pipeline import run_pipeline

        with get_session() as session:
            run_pipeline(session, OllamaClient())

    await asyncio.to_thread(_run)
    return RedirectResponse("/", status_code=303)
