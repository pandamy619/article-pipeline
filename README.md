# article-pipeline

Пайплайн поиска статей и публикации их в Telegram-группу с использованием **локальной нейросети**. Поиск и рерайт делает локальная LLM (Qwen3 через Ollama), перед публикацией каждый пост проходит **проверку человеком**.

## Возможности

- Сбор статей из нескольких источников: RSS, arXiv, Habr, Reddit, веб-поиск (SearXNG), другие Telegram-каналы.
- Дедупликация (по URL и семантически, через эмбеддинги).
- AI-оценка релевантности и рерайт поста на русском языке.
- Модерация через бота: черновик приходит в личку с кнопками ✅ / ✏️ / ❌.
- Публикация одобренного поста в группу.

## Стек

Python · Ollama (Qwen3-14B) · bge-m3 · PostgreSQL · Valkey · SearXNG · aiogram · Telethon · Docker.
Подробнее — в [docs/architecture.md](docs/architecture.md) и [docs/repo-architecture.md](docs/repo-architecture.md).

## Структура

```
app/      — сервис (сбор, фильтр, рерайт, бот, публикация)
deploy/   — docker-compose, .env.example, конфиг SearXNG
docs/     — архитектура и описание стека
```

## Быстрый старт

**Разработка (Mac):** Ollama ставится нативно, остальное — в Docker.

```bash
brew install ollama && ollama serve
ollama pull qwen3:4b && ollama pull bge-m3
cp deploy/.env.example deploy/.env   # заполнить токены
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml up postgres valkey searxng app
```

**Прод (Windows + RTX 4080):** всё в Docker, Ollama с GPU.

```bash
cp deploy/.env.example deploy/.env   # заполнить токены
docker compose -f deploy/docker-compose.yml up -d
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
