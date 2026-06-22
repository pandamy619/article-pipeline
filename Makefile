# Команды для разработки (Mac). Прод на Windows — см. docs/deploy-windows.md
COMPOSE = docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml
# Прод (Windows + GPU): без dev-оверрайда, с профилем gpu (ollama в контейнере)
PROD = docker compose -f deploy/docker-compose.yml --profile gpu

.PHONY: up down logs ps collect migrate reset reset-all clean test \
        prod-up prod-down prod-logs prod-ps prod-collect

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

# --- Прод (Windows + GPU) ---
# поднять весь стек с GPU-Ollama (модели подтянутся автоматически при первом запуске)
prod-up:
	$(PROD) up -d --build

prod-down:
	$(PROD) down

prod-logs:
	$(PROD) logs -f

prod-ps:
	$(PROD) ps

# разовый прогон пайплайна на проде
prod-collect:
	$(PROD) exec app python -m src collect
