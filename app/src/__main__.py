"""Точка входа.

python -m src           — запуск бота модерации + планировщик пайплайна
python -m src collect   — один прогон пайплайна (сбор -> фильтр -> рерайт) и выход
"""

from __future__ import annotations

import sys


def _collect_once() -> None:
    from src.db.base import get_session
    from src.llm.client import OllamaClient
    from src.pipeline import run_pipeline

    client = OllamaClient()
    with get_session() as session:
        result = run_pipeline(session, client)
    print(result)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "collect":
        _collect_once()
        return

    import asyncio

    from src.moderation.bot import run

    asyncio.run(run())


if __name__ == "__main__":
    main()
