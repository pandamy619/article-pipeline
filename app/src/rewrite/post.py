"""Генерация поста для Telegram из статьи (рерайт на русском)."""

from __future__ import annotations

from typing import Protocol

from src.collectors.base import Article

TELEGRAM_LIMIT = 4096

SYSTEM_PROMPT = (
    "Ты — редактор Telegram-канала для начинающих программистов. "
    "По статье напиши КОРОТКИЙ пост на русском языке: "
    "цепляющий заголовок первой строкой, затем 2–3 предложения по сути "
    "(чем полезно новичку), в конце 2–3 хэштега. "
    "Только суть, без пересказа всей статьи, простым языком, без воды, "
    "не выдумывай фактов, без markdown-заголовков. "
    "Весь пост — не длиннее 700 символов. "
    "Не добавляй ссылку на источник — её добавят автоматически."
)


class Generator(Protocol):
    def generate(
        self, prompt: str, *, system: str | None = None, format: str | None = None
    ) -> str: ...


def build_prompt(article: Article) -> str:
    text = article.text[:3000]
    return f"Заголовок: {article.title}\nИсточник: {article.source}\n\nТекст:\n{text}"


def _assemble(body: str, url: str, limit: int = TELEGRAM_LIMIT) -> str:
    body = body.strip()
    tail = f"\n\nИсточник: {url}"
    if len(body) + len(tail) > limit:
        body = body[: limit - len(tail) - 1].rstrip() + "…"
    return body + tail


def generate_post(
    article: Article, *, client: Generator, limit: int = TELEGRAM_LIMIT
) -> str:
    body = client.generate(build_prompt(article), system=SYSTEM_PROMPT)
    return _assemble(body, article.url, limit=limit)
