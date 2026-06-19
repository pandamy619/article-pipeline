# Архитектура репозитория, лицензии и кросс-платформа

Хостинг — GitHub. Разработка — на Mac (Apple Silicon), деплой — на Windows-ПК с RTX 4080.

---

## 1. Монорепо vs много репозиториев

Для этого проекта — **монорепо** (один репозиторий). Это единая система, один разработчик, общие модели/конфиги, и деплоится всё одним `docker compose`. Несколько репозиториев дали бы только лишние накладные расходы (синхронизация версий, отдельные CI). Разделять есть смысл позже, если бот/сборщик/веб-админка превратятся в независимые сервисы со своими релизами.

## 2. Структура папок

```
article-pipeline/
├─ .github/
│  └─ workflows/
│     └─ ci.yml                 # lint + build образа (GitHub Actions)
├─ app/                         # основной сервис (Python)
│  ├─ Dockerfile
│  ├─ pyproject.toml            # зависимости (uv или poetry)
│  ├─ src/
│  │  ├─ collectors/            # rss, arxiv, reddit, telethon, searxng
│  │  ├─ dedup/                 # эмбеддинги + сравнение
│  │  ├─ filter/                # оценка релевантности (LLM)
│  │  ├─ rewrite/               # рерайт постов (LLM)
│  │  ├─ moderation/            # очередь + бот с кнопками
│  │  ├─ publisher/             # отправка в Telegram-группу
│  │  ├─ llm/                   # клиент к Ollama
│  │  ├─ db/                    # модели + миграции (alembic)
│  │  └─ config.py
│  ├─ scripts/
│  │  └─ make_session.py        # разовая генерация Telethon .session
│  └─ tests/
├─ deploy/
│  ├─ docker-compose.yml        # прод (Windows + GPU)
│  ├─ docker-compose.dev.yml    # оверрайд для Mac (без GPU, hot-reload)
│  ├─ .env.example
│  └─ searxng/
│     └─ settings.yml
├─ docs/
│  └─ architecture.md           # схема и стек
├─ sessions/                    # .session Telethon (в .gitignore!)
├─ .gitignore
├─ .gitattributes               # eol=lf — критично для Mac→Windows
├─ .dockerignore
├─ .editorconfig
├─ README.md
└─ LICENSE
```

## 3. Ветки и процесс

Простой **GitHub Flow** (для соло-разработчика этого хватает):

- `main` — всегда деплоится, защищена (require PR, require CI green).
- `feature/...` — ветка под задачу → Pull Request → merge в `main`.
- Тег `v1.0.0` (semver) — триггерит сборку и публикацию образа.

## 4. CI/CD (всё бесплатно на GitHub)

- **GitHub Actions** — бесплатно без лимита для публичных репозиториев; для приватных есть бесплатный месячный лимит минут.
- **GHCR (GitHub Container Registry)** — хранение Docker-образов; бесплатно для публичных, с бесплатной квотой для приватных.
- Пайплайн CI: `ruff` (линт+формат) → сборка `app`-образа под `linux/amd64` (целевая платформа — Windows-ПК) → по тегу пуш образа в GHCR.
- Деплой на Windows: либо `git pull` + `docker compose up -d --build`, либо `docker compose pull` готового образа из GHCR + `up -d`.

## 5. Секреты — что НЕ коммитить

В `.gitignore` обязательно: `.env`, `*.session` (Telethon — это полноценный доступ к аккаунту!), локальные данные БД, кэш моделей. В репозитории — только `.env.example`. Для CI секреты живут в **GitHub → Settings → Secrets**, на Windows-хосте реальный `.env` лежит локально.

---

## 6. Аудит лицензий — всё бесплатно для тебя

Проверено на июнь 2026. Рекомендованный стек целиком бесплатен; почти всё — OSI-опенсорс.

| Компонент | Лицензия | Статус |
|---|---|---|
| **Qwen3-14B** (модель) | Apache 2.0 | ✅ Открытая, в т.ч. коммерческое использование |
| **Ollama** | MIT | ✅ Открытая |
| **bge-m3** (эмбеддинги) | MIT | ✅ Открытая |
| **PostgreSQL** | PostgreSQL License (BSD-like) | ✅ Открытая |
| **SearXNG** | AGPL-3.0 | ✅ Открытая (для self-host без проблем) |
| **Telethon** | MIT | ✅ Открытая |
| **aiogram** | MIT | ✅ Открытая |
| **feedparser** | BSD | ✅ Открытая |
| **PRAW** (Reddit) | BSD | ✅ Открытая (сам Reddit API — бесплатный тариф с лимитами) |
| **trafilatura** | Apache 2.0 | ✅ Открытая |
| **Redis** | AGPL-3.0 (с Redis 8) | ✅ Открытая. Альтернатива — **Valkey** (BSD) |
| **n8n** | Sustainable Use License | ⚠️ Source-available «fair-code», не OSI |
| **Docker Desktop** | Docker Subscription | ⚠️ Бесплатно для личного и малого бизнеса; GUI не open source |

### Два нюанса и их свободные замены

**n8n** — это «fair-code»: исходники открыты, self-hosted Community Edition **полностью бесплатна и без лимитов** для твоего использования, но это не OSI-лицензия и есть ограничения на перепродажу. n8n у нас опционален (оркестрация). Если хочется 100% OSI — замени на **Prefect** (Apache 2.0) или обычный **cron**.

**Docker Desktop** — для тебя (личное использование / малый бизнес: < 250 сотрудников и < $10M выручки) **бесплатен**. Платным он становится только для крупных компаний. Если нужен полностью открытый вариант без всяких порогов: **Rancher Desktop** (Apache 2.0), **Podman** (Apache 2.0), на Mac ещё **Colima**. Сам движок Docker Engine (CLI/демон) — Apache 2.0 и бесплатен всегда; платная только GUI-обёртка Desktop.

**Про AGPL (Redis 8, SearXNG):** копилефт AGPL срабатывает, только если ты распространяешь модифицированный сетевой сервис третьим лицам. Для личного self-hosted бота никаких обязательств не возникает. Если хочется вообще без AGPL — возьми **Valkey** вместо Redis.

**Итог:** рекомендованный стек = 0 рублей и почти весь — настоящий открытый исходник. Полностью-OSI-вариант: Qwen3 + Ollama + PostgreSQL + **Valkey** + SearXNG + Python-библиотеки + **Prefect/cron** вместо n8n + **Rancher Desktop/Podman** вместо Docker Desktop.

---

## 7. Разработка на Mac → деплой на Windows

Docker сглаживает разницу ОС, но есть три реальных момента.

### 7.1. Архитектура CPU: ARM (Mac) vs x86 (Windows)

Mac на Apple Silicon — это `arm64`, Windows-ПК — `amd64`. Официальные образы (python, postgres, redis/valkey, ollama, searxng) **мультиарх** и работают на обоих. Для своего `app`-образа:

- Локально на Mac собирается под arm64 автоматически — для разработки ок.
- В CI собирай образ под **`linux/amd64`** (это то, что поедет на Windows). При желании — мультиарч через `docker buildx build --platform linux/amd64,linux/arm64`.
- Не «запекай» в образ платформозависимые бинарники; ставь зависимости через pip/uv внутри Dockerfile.

### 7.2. GPU есть только на Windows

На Mac нет NVIDIA, а Ollama-в-Docker использует CUDA. Поэтому:

- **На Mac (dev):** запусти **Ollama нативно** (приложение для macOS, использует GPU Apple через Metal), а контейнер `app` обращается к ней по `http://host.docker.internal:11434`. Для скорости на деве можно взять модель поменьше — `qwen3:4b`.
- **На Windows (prod):** Ollama в контейнере с пробросом GPU (как в `docker-compose.yml`), модель `qwen3:14b`.
- Разницу задаёт `docker-compose.dev.yml`: указывает `OLLAMA_HOST=host.docker.internal`, монтирует исходники для hot-reload и ставит малую модель. На Mac запускаешь без сервиса `ollama`:
  ```
  docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml up postgres redis searxng app
  ```

### 7.3. Переносы строк (CRLF/LF)

Главная незаметная боль Mac↔Windows. Файл `.gitattributes` с `* text=auto eol=lf` гарантирует, что скрипты и Dockerfile останутся с LF — иначе bash в контейнерах на Windows будет падать с `\r`-ошибками. Это обязательный файл.

### 7.4. Прочее

- `.editorconfig` — единый стиль (отступы, LF) в любом редакторе на обеих ОС.
- `.wslconfig` на Windows — ограничить RAM для WSL2.
- Пути — только относительные/через переменные, без `C:\...` и без `/Users/...` в коде.

---

## 8. Лицензия твоего репозитория

Если репозиторий приватный (личный бот) — выбор лицензии не критичен. Если выкладываешь в открытый доступ — подойдёт **MIT** (максимально просто) или **Apache 2.0** (с патентной оговоркой). AGPL-зависимости (SearXNG, Redis 8) на твою лицензию не влияют, пока ты не распространяешь их как модифицированный сервис.
