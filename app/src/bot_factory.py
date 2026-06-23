"""Создание Bot с опциональным прокси.

Нужно для сетей, где api.telegram.org недоступен напрямую (TELEGRAM_PROXY).
"""

from __future__ import annotations

import logging
import re

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from src.config import settings

log = logging.getLogger(__name__)
_SUPPORTED = ("socks5://", "socks4://", "http://")


def _proxy() -> str:
    # терпим затесавшийся пробел/инлайн-комментарий в значении из .env
    raw = re.split(r"\s#", settings.telegram_proxy, maxsplit=1)[0]
    proxy = raw.strip()
    if proxy and not proxy.lower().startswith(_SUPPORTED):
        # https:// и прочие схемы python_socks не понимает — игнорируем, идём напрямую
        log.warning(
            "TELEGRAM_PROXY: неподдерживаемая схема '%s' — игнорирую прокси, иду "
            "напрямую. Поддерживаются socks5:// | socks4:// | http://",
            proxy.split("://", 1)[0],
        )
        return ""
    return proxy


def make_bot(token: str) -> Bot:
    proxy = _proxy()
    if proxy:
        return Bot(token, session=AiohttpSession(proxy=proxy))
    return Bot(token)
