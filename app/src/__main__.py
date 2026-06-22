"""Точка входа.

python -m src           — запуск бота модерации + планировщик пайплайна
python -m src collect   — один прогон пайплайна (сбор -> фильтр -> рерайт) и выход
"""

from __future__ import annotations

import logging
import sys

log = logging.getLogger("src")


def _collect_once() -> None:
    from src.db.base import get_session
    from src.llm.client import OllamaClient
    from src.log import setup_logging
    from src.pipeline import run_all_channels
    from src.settings_store import apply_overrides

    setup_logging()
    with get_session() as session:
        apply_overrides(session)
        result = run_all_channels(session, OllamaClient())
    log.info("pipeline result: %s", result)


def main() -> None:
    from src.log import setup_logging

    setup_logging()
    if len(sys.argv) > 1 and sys.argv[1] == "collect":
        _collect_once()
        return

    import asyncio

    from src.moderation.bot import run

    asyncio.run(run())


if __name__ == "__main__":
    main()
