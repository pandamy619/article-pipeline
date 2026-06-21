"""Генерация поста для Telegram из статьи (рерайт на русском)."""

from __future__ import annotations

import json
import re
from typing import Protocol

from src.collectors.base import Article

TELEGRAM_LIMIT = 4096

SYSTEM_PROMPT = (
    "Ты — редактор Telegram-канала для начинающих программистов. "
    "По статье составь короткий готовый пост на русском языке: "
    "цепляющий заголовок первой строкой, затем 2–3 предложения по сути "
    "(чем полезно новичку), в конце 2–3 хэштега. "
    "Только суть, без пересказа всей статьи, простым языком, без воды, "
    "не выдумывай фактов, без markdown-заголовков, не длиннее 700 символов, "
    "без ссылки на источник (её добавят автоматически). "
    'Ответь СТРОГО в JSON: {"post": "<готовый текст поста>"}.'
)


class Generator(Protocol):
    def generate(
        self, prompt: str, *, system: str | None = None, format: str | None = None
    ) -> str: ...


def build_prompt(article: Article) -> str:
    text = article.text[:3000]
    return f"Заголовок: {article.title}\nИсточник: {article.source}\n\nТекст:\n{text}"


def _extract_post(raw: str) -> str:
    """Достаёт текст поста из JSON-ответа; терпит <think> и текст вокруг."""
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    candidates = [cleaned]
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        candidates.append(match.group())
    for candidate in candidates:
        try:
            data = json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("post"):
            return str(data["post"]).strip()
    # фолбэк: вытащить значение "post" даже из обрезанного/битого JSON
    truncated = re.search(r'"post"\s*:\s*"(.*)', cleaned, re.DOTALL)
    if truncated:
        value = truncated.group(1).strip().rstrip("}").strip()
        if value.endswith('"'):
            value = value[:-1]
        return value.replace('\\"', '"').replace("\\n", "\n").strip()
    return cleaned


def _assemble(body: str, url: str, limit: int = TELEGRAM_LIMIT) -> str:
    body = body.strip()
    tail = f"\n\nИсточник: {url}"
    if len(body) + len(tail) > limit:
        body = body[: limit - len(tail) - 1].rstrip() + "…"
    return body + tail


def generate_post(
    article: Article, *, client: Generator, limit: int = TELEGRAM_LIMIT
) -> str:
    raw = client.generate(build_prompt(article), system=SYSTEM_PROMPT, format="json")
    return _assemble(_extract_post(raw), article.url, limit=limit)
