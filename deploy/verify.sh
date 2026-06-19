#!/usr/bin/env bash
# Проверка связности локальной инфраструктуры (шаг 3).
# Запуск из корня репозитория:  bash deploy/verify.sh
set -u

COMPOSE="docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml"
ok=0; fail=0

check() {
  if eval "$2" >/dev/null 2>&1; then
    echo "✅ $1"; ok=$((ok + 1))
  else
    echo "❌ $1"; fail=$((fail + 1))
  fi
}

check "Ollama (нативная на хосте)"     "curl -fsS http://localhost:11434/api/tags"
check "Postgres принимает соединения"  "$COMPOSE exec -T postgres pg_isready"
check "Valkey отвечает PONG"           "$COMPOSE exec -T valkey valkey-cli ping | grep -q PONG"
check "SearXNG отдаёт JSON"            "curl -fsS 'http://localhost:8080/search?q=test&format=json'"
check "app собран и видит Ollama"      "$COMPOSE run --rm --no-deps app python -c \"import urllib.request,os; urllib.request.urlopen(os.environ['OLLAMA_HOST']+'/api/tags')\""

echo "--------"
echo "Итог: $ok ✅ / $fail ❌"
[ "$fail" -eq 0 ] && echo "Шаг 3 готов." || { echo "Есть проблемы — см. выше."; exit 1; }
