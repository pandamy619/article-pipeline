"""Рантайм-настройки в БД поверх .env: редактируются из админки.

Значения хранятся строками; apply_overrides() накатывает их на singleton
settings текущего процесса. Пайплайн применяет это в начале каждого прогона,
админка — на каждый запрос.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.db.models import AppSetting

# Только ГЛОБАЛЬНЫЕ ключи (на весь сервис). Тематика, порог, источники,
# интервалы сбора/публикации — это настройки ПРОЕКТА (вкладка «Проекты»),
# здесь их быть не должно, иначе дублирование.
EDITABLE: dict[str, str] = {
    "llm_model": "str",
    "embed_model": "str",
    "max_articles_per_run": "int",
    "semantic_dedup_enabled": "bool",
    "semantic_dedup_threshold": "float",
    # ключи поиска картинок (Фаза 2) — глобальные, на весь сервис
    "pexels_api_key": "str",
    "pixabay_api_key": "str",
}


def _cast(kind: str, raw: str):
    if kind == "int":
        return int(raw)
    if kind == "float":
        return float(raw)
    if kind == "bool":
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return raw


def get_overrides(session: Session) -> dict[str, str]:
    rows = session.scalars(select(AppSetting)).all()
    return {r.key: r.value for r in rows if r.key in EDITABLE}


def set_override(session: Session, key: str, value: str) -> bool:
    if key not in EDITABLE:
        return False
    rec = session.get(AppSetting, key)
    if rec:
        rec.value = value
    else:
        session.add(AppSetting(key=key, value=value))
    session.flush()
    return True


def apply_overrides(session: Session) -> None:
    """Накатывает значения из БД на singleton settings (для текущего процесса)."""
    for key, raw in get_overrides(session).items():
        try:
            setattr(settings, key, _cast(EDITABLE[key], raw))
        except (ValueError, TypeError):
            continue


def current_values(session: Session) -> dict[str, object]:
    """Актуальные значения (env + оверрайды) для показа в админке."""
    apply_overrides(session)
    return {key: getattr(settings, key) for key in EDITABLE}
