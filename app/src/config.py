"""Конфигурация приложения из переменных окружения (.env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"

    # LLM
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "qwen3:4b"
    embed_model: str = "bge-m3"

    # Хранилище
    database_url: str = ""
    redis_url: str = ""
    searxng_url: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""
    admin_user_id: str = ""

    # Поведение
    relevance_threshold: int = 7

    # Источники
    rss_feeds: str = ""  # список URL через запятую

    @property
    def rss_feed_list(self) -> list[str]:
        return [u.strip() for u in self.rss_feeds.split(",") if u.strip()]


settings = Settings()
