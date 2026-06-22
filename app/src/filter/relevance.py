"""Оценка релевантности статьи тематике канала локальной LLM."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from src.collectors.base import Article
from src.config import settings


def _system_prompt() -> str:
    return (
        "Ты — строгий редактор Telegram-канала. Тематика канала: "
        f"{settings.channel_topic}. "
        "Оцени, насколько статья подходит каналу, по шкале 0–10.\n"
        "8–10 — обучающие материалы: туториалы, разбор основ, гайды, "
        "пошаговые объяснения концепций для новичков.\n"
        "0–4 — НЕ подходит, даже если упоминается программирование: новости "
        "индустрии, релизы и анонсы, карьера/зарплаты/рынок труда, "
        "подборки и «ТОП-N», реклама, мнения, вода, узкий хардкор для сеньоров.\n"
        'Ответь СТРОГО в JSON: {"score": <целое 0-10>, '
        '"reason": "<одно короткое предложение по-русски, не больше 15 слов>"}.'
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


def _extract_json(raw: str) -> dict | None:
    """Достаёт JSON-объект из ответа модели (терпит <think> и текст вокруг)."""
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    for candidate in (cleaned, _first_brace_block(cleaned)):
        if not candidate:
            continue
        try:
            data = json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _first_brace_block(text: str) -> str | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group() if match else None


def _parse(raw: str) -> RelevanceResult:
    score = 0
    reason = ""
    data = _extract_json(raw)
    if data is not None:
        try:
            score = int(data.get("score", 0))
        except (ValueError, TypeError):
            score = 0
        reason = str(data.get("reason", ""))
    score = max(0, min(10, score))
    return RelevanceResult(score=score, reason=reason)


def score_relevance(article: Article, *, client: Scorer) -> RelevanceResult:
    raw = client.generate(build_prompt(article), system=_system_prompt(), format="json")
    return _parse(raw)


def is_relevant(result: RelevanceResult, threshold: int | None = None) -> bool:
    t = settings.relevance_threshold if threshold is None else threshold
    return result.score >= t
