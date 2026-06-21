# Команды для разработки (Mac). Прод на Windows — см. README.
COMPOSE = docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml

.PHONY: up down logs ps collect migrate reset test

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

# очистить все статьи (перепрогон с нуля)
reset:
	$(COMPOSE) exec app python -c "from src.db.base import SessionLocal; from src.db.models import ArticleRecord; s=SessionLocal(); n=s.query(ArticleRecord).delete(); s.commit(); s.close(); print('deleted', n)"

# тесты + линтер
test:
	cd app && poetry run pytest -q && poetry run ruff check .
