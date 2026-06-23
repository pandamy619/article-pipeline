"""Создание Bot с опциональным прокси.

Нужно для сетей, где api.telegram.org недоступен напрямую (TELEGRAM_PROXY).
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from src.config import settings


def make_bot(token: str) -> Bot:
    if settings.telegram_proxy:
        return Bot(token, session=AiohttpSession(proxy=settings.telegram_proxy))
    return Bot(token)
