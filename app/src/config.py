"""Конфигурация приложения из переменных окружения (.env)."""

import re

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    log_level: str = "INFO"

    # LLM
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "qwen3:4b"
    embed_model: str = "bge-m3"

    # Хранилище
    database_url: str = ""
    redis_url: str = ""
    searxng_url: str = ""

    # Поиск картинок (Фаза 2): бесплатные сток-API + SearXNG (уже есть выше)
    pexels_api_key: str = ""
    pixabay_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""
    admin_user_id: str = ""
    admin_token: str = ""  # токен для входа в веб-админку; пусто = без авторизации
    telegram_proxy: str = ""  # http://host:port — если api.telegram.org заблокирован
    media_dir: str = "media"  # папка для своих/сгенерированных картинок (том в проде)

    # Поведение
    relevance_threshold: int = 7
    run_interval_minutes: int = 60
    publish_interval_minutes: int = 120  # шаг между авто-запланированными постами
    max_articles_per_run: int = 0  # 0 = без лимита
    channel_topic: str = (
        "статьи для начинающих программистов: туториалы, основы, "
        "разбор базовых концепций, первые языки и инструменты, вход в профессию"
    )

    # Семантический дедуп (эмбеддинги bge-m3)
    semantic_dedup_enabled: bool = True
    semantic_dedup_threshold: float = 0.88  # косинус 0..1; выше = строже к дублям
    semantic_dedup_window: int = 300  # с каким числом последних статей сравнивать

    # Источники
    rss_feeds: str = ""  # список URL через запятую

    # Habr (русский, включён по умолчанию; пустые хабы = общая RU-лента)
    habr_enabled: bool = True
    habr_hubs: str = ""  # алиасы хабов через запятую, напр. programming,python

    # arXiv (англоязычный; пустые категории = выключено)
    arxiv_categories: str = ""  # коды через запятую, напр. cs.SE,cs.PL
    arxiv_max_results: int = 10

    # Reddit (англоязычный; пустые сабреддиты = выключено)
    reddit_subreddits: str = ""  # имена без r/, напр. learnprogramming
    reddit_period: str = "week"  # hour|day|week|month|year|all
    reddit_limit: int = 10

    # Веб-поиск (SearXNG; пустые запросы = выключено)
    searxng_queries: str = ""  # запросы через запятую
    searxng_language: str = "ru"
    searxng_max_results: int = 10

    @staticmethod
    def _split(raw: str) -> list[str]:
        """Список из значения env: терпит инлайн-комментарии и мусор.

        URL/алиасы/коды/имена сабреддитов не содержат пробелов, поэтому
        токены с пробелами и начинающиеся с '#' отбрасываем — это защита
        от случайно попавшего в значение комментария из .env.
        """
        raw = re.split(r"\s#", raw, maxsplit=1)[0]  # срезаем инлайн-комментарий " #..."
        out: list[str] = []
        for token in raw.split(","):
            token = token.strip()
            if token and not token.startswith("#") and " " not in token:
                out.append(token)
        return out

    @property
    def rss_feed_list(self) -> list[str]:
        return self._split(self.rss_feeds)

    @property
    def habr_hub_list(self) -> list[str]:
        return self._split(self.habr_hubs)

    @property
    def arxiv_category_list(self) -> list[str]:
        return self._split(self.arxiv_categories)

    @property
    def reddit_subreddit_list(self) -> list[str]:
        return self._split(self.reddit_subreddits)

    @property
    def searxng_query_list(self) -> list[str]:
        return self._split(self.searxng_queries)


settings = Settings()
