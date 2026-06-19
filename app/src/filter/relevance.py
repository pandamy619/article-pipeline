"""Оценка релевантности статьи тематике канала локальной LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from src.collectors.base import Article
from src.config import settings

CHANNEL_TOPIC = (
    "статьи для начинающих программистов: основы, туториалы, вход в профессию, "
    "первые языки и инструменты, разбор базовых концепций"
)

SYSTEM_PROMPT = (
    "Ты — редактор Telegram-канала. Тематика канала: "
    f"{CHANNEL_TOPIC}. "
    "Оцени, насколько статья подходит каналу, по шкале от 0 до 10: "
    "10 — отлично заходит новичку, 0 — не подходит (узкий хардкор для сеньоров, "
    "не про программирование, реклама, вода). "
    'Ответь СТРОГО в JSON: {"score": <целое 0-10>, "reason": "<кратко по-русски>"}.'
)


class Scorer(Protocol):
    def generate(
        self, prompt: str, *, system: str | None = None, format: str | None = None
    ) -> str: ...


@dataclass(slots=True)
class RelevanceResult:
    score: int
    reason: str


def build_prompt(article: Article) -> str:
    text = article.text[:2000]
    return f"Заголовок: {article.title}\nИсточник: {article.source}\n\nТекст:\n{text}"


def _parse(raw: str) -> RelevanceResult:
    score = 0
    reason = ""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            score = int(data.get("score", 0))
            reason = str(data.get("reason", ""))
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    score = max(0, min(10, score))
    return RelevanceResult(score=score, reason=reason)


def score_relevance(article: Article, *, client: Scorer) -> RelevanceResult:
    raw = client.generate(build_prompt(article), system=SYSTEM_PROMPT, format="json")
    return _parse(raw)


def is_relevant(result: RelevanceResult, threshold: int | None = None) -> bool:
    t = settings.relevance_threshold if threshold is None else threshold
    return result.score >= t
