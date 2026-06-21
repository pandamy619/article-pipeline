FROM python:3.12-slim

WORKDIR /app

# Системные зависимости для lxml / trafilatura
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Poetry: ставим зависимости в системный python (без отдельного venv)
RUN pip install --no-cache-dir poetry
ENV POETRY_VIRTUALENVS_CREATE=false

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main

COPY . .

# миграции применяются на старте, затем запуск бота + планировщика
CMD ["sh", "-c", "alembic upgrade head && python -m src"]
