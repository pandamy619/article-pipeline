# Dev на Mac (Ollama нативная). Windows-прод (GPU) — цели win-* ниже.
# На Windows make запускают из WSL или git-bash (choco install make / wsl).
COMPOSE = docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml
# Прод (Windows + GPU): без dev-оверрайда, с профилем gpu (ollama в контейнере)
PROD = docker compose -f deploy/docker-compose.yml --profile gpu

.PHONY: up down logs ps collect migrate reset reset-all clean test \
        win-up win-down win-logs win-app win-ps win-pull win-migrate win-collect

# поднять весь стек (dev; Ollama — нативная, не в Docker)
up:
	$(COMPOSE) up -d --build

# остановить
down:
	$(COMPOSE) down

# логи всех сервисов
logs:
	$(COMPOSE) logs -f

# статус контейнеров
ps:
	$(COMPOSE) ps

# разовый прогон пайплайна
collect:
	$(COMPOSE) exec app python -m src collect

# применить миграции вручную
migrate:
	$(COMPOSE) exec app alembic upgrade head

# очистить ТОЛЬКО new/filtered/rejected (черновики, pending и опубликованные сохраняются)
reset:
	$(COMPOSE) exec app python -c "from src.db.base import SessionLocal; from src.db.models import ArticleRecord, ArticleStatus; s=SessionLocal(); n=s.query(ArticleRecord).filter(ArticleRecord.status.in_([ArticleStatus.new, ArticleStatus.filtered, ArticleStatus.rejected])).delete(synchronize_session=False); s.commit(); s.close(); print('deleted', n)"

# удалить ВСЕ статьи, включая черновики и опубликованные
reset-all:
	$(COMPOSE) exec app python -c "from src.db.base import SessionLocal; from src.db.models import ArticleRecord; s=SessionLocal(); n=s.query(ArticleRecord).delete(); s.commit(); s.close(); print('deleted', n)"

# СНЕСТИ ВСЁ: контейнеры + тома (вся БД будет удалена!)
clean:
	$(COMPOSE) down -v

# тесты + линтер
test:
	cd app && poetry run pytest -q && poetry run ruff check .

# --- Windows (прод, GPU) ---
# СБОРКА И ЗАПУСК всего стека на Windows с GPU-Ollama
# (модели подтянутся автоматически при первом запуске — это долго)
win-up:
	$(PROD) up -d --build

# остановить
win-down:
	$(PROD) down

# логи всех сервисов
win-logs:
	$(PROD) logs -f

# логи только основного сервиса (бот + планировщик)
win-app:
	$(PROD) logs -f app

# статус контейнеров
win-ps:
	$(PROD) ps

# пере-скачать модели из .env (LLM_MODEL / EMBED_MODEL)
win-pull:
	$(PROD) up -d ollama-pull

# применить миграции вручную (обычно app делает это сам при старте)
win-migrate:
	$(PROD) exec app alembic upgrade head

# разовый прогон пайплайна
win-collect:
	$(PROD) exec app python -m src collect
