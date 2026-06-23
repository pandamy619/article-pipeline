"""Создание Bot с опциональным прокси.

Нужно для сетей, где api.telegram.org недоступен напрямую (TELEGRAM_PROXY).
"""

from __future__ import annotations

import re

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from src.config import settings


def _proxy() -> str:
    # терпим затесавшийся пробел/инлайн-комментарий в значении из .env
    raw = re.split(r"\s#", settings.telegram_proxy, maxsplit=1)[0]
    return raw.strip()


def make_bot(token: str) -> Bot:
    proxy = _proxy()
    if proxy:
        return Bot(token, session=AiohttpSession(proxy=proxy))
    return Bot(token)
