# Деплой на Windows-ПК (RTX 4080, GPU)

Прод крутится в Docker: контейнер **Ollama с доступом к GPU** + Postgres, Valkey,
SearXNG, бэкенд (сборщик/фильтр/рерайт/бот), админка и фронтенд. Модели LLM
тянутся автоматически при первом запуске.

## 1. Предусловия (один раз)

1. **Драйвер NVIDIA** — свежий Game Ready / Studio driver (в нём уже есть поддержка
   CUDA в WSL2). Проверь в PowerShell: `nvidia-smi` должен показать RTX 4080.
2. **WSL2** — в PowerShell от админа:
   ```powershell
   wsl --install
   ```
   и перезагрузка.
3. **Docker Desktop** — установить, в Settings → General включить «Use the WSL 2
   based engine», в Settings → Resources → WSL integration включить интеграцию с
   дистрибутивом.
4. **Git** — установить, чтобы клонировать репозиторий.

### Проверка, что GPU виден из Docker

```powershell
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

Должна появиться таблица с RTX 4080. Если ошибка — проблема в драйвере/WSL, дальше
идти нет смысла.

## 2. Код и секреты

```powershell
git clone https://github.com/pandamy619/article-pipeline.git
cd article-pipeline
copy deploy\.env.example deploy\.env
```

Открой `deploy\.env` и заполни:

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` (`-100…`), `ADMIN_USER_ID`
- `SEARXNG_SECRET` (сгенерируй: `openssl rand -hex 32` в WSL)
- `POSTGRES_PASSWORD` (задай надёжный)
- `LLM_MODEL` — на 16 ГБ хорошо идёт `qwen2.5:7b` или `qwen3:14b`; `EMBED_MODEL=bge-m3`
- источники (`RSS_FEEDS`, `HABR_HUBS`, при желании `ARXIV_CATEGORIES`,
  `REDDIT_SUBREDDITS`, `SEARXNG_QUERIES`)

Комментарии в `.env` пиши только на отдельных строках, не после значения.

> Бот должен быть **администратором канала**, иначе публикация не пройдёт.

## 3. Запуск

```powershell
docker compose -f deploy/docker-compose.yml --profile gpu up -d --build
```

(или `make prod-up`, если установлен make в WSL)

Что происходит: поднимается Ollama с GPU, сервис `ollama-pull` тянет модели из
`.env` (первый раз долго — гигабайты), стартуют Postgres/Valkey/SearXNG, затем
бэкенд (он **сам применяет миграции** при старте), админка и фронтенд.

Следить за загрузкой моделей:

```powershell
docker compose -f deploy/docker-compose.yml logs -f ollama-pull
```

## 4. Проверка

- Статусы контейнеров: `docker compose -f deploy/docker-compose.yml ps`
- Админка: <http://localhost:8000/api/stats> (JSON со счётчиками)
- Фронтенд: <http://localhost:3000>
- GPU во время работы: `docker exec ollama nvidia-smi` — при прогоне видна загрузка.

Разовый прогон пайплайна (не дожидаясь планировщика):

```powershell
docker compose -f deploy/docker-compose.yml exec app python -m src collect
```

(или `make prod-collect`)

Дальше пайплайн крутится по расписанию (`RUN_INTERVAL_MINUTES`). Черновики
приходят на модерацию в Telegram (`ADMIN_USER_ID`) и/или видны в админке; после
аппрува пост уходит в канал.

## 5. Обновление версии

```powershell
git pull
docker compose -f deploy/docker-compose.yml --profile gpu up -d --build app admin web
```

Миграции применятся автоматически при рестарте `app`. Если в `.env` сменил модель —
один раз дёрни загрузку: `docker compose -f deploy/docker-compose.yml --profile gpu up -d ollama-pull`.

## 6. Автозапуск

В Docker Desktop включи «Start Docker Desktop when you log in». У всех сервисов
стоит `restart: unless-stopped`, так что после перезагрузки ПК стек поднимется сам.

## 7. Если что-то не так

- **GPU не виден контейнеру** — обнови драйвер NVIDIA, перезапусти WSL
  (`wsl --shutdown`) и Docker Desktop; повтори проверку из шага 1.
- **Модель не помещается / OOM** — поставь модель меньше в `LLM_MODEL`
  (например, `qwen2.5:7b`) и пере-дёрни `ollama-pull`.
- **Порт занят** (8000/3000/8080/11434) — освободи порт или поменяй маппинг в
  `deploy/docker-compose.yml`.
- **Бот не постит** — проверь, что бот админ канала и `TELEGRAM_CHANNEL_ID`
  начинается с `-100`.
- **Логи**: `docker compose -f deploy/docker-compose.yml logs -f app` (или `admin`).
