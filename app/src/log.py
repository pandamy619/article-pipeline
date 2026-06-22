"""Единая настройка логирования (вызывается из точек входа)."""

from __future__ import annotations

import logging

from src.config import settings

_CONFIGURED = False


def setup_logging(level: str | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=(level or settings.log_level).upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _CONFIGURED = True
