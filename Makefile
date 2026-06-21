# Команды для разработки (Mac). Прод на Windows — см. README.
COMPOSE = docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml

.PHONY: up down logs ps collect migrate test

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

# тесты + линтер
test:
	cd app && poetry run pytest -q && poetry run ruff check .
