"""Точка входа. Пока — заглушка каркаса; логика добавляется по задачам бэклога."""
from src.config import settings


def main() -> None:
    print(f"article-pipeline scaffold OK (env={settings.env}, model={settings.llm_model})")


if __name__ == "__main__":
    main()
