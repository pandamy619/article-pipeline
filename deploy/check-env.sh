#!/usr/bin/env bash
# Проверяет, что в .env заполнены все ключи из .env.example (без заглушек).
# Запуск из корня репозитория:  bash deploy/check-env.sh [путь_к_env]
set -u

EXAMPLE="deploy/.env.example"
ENVFILE="${1:-deploy/.env}"

[ -f "$ENVFILE" ] || { echo "Нет $ENVFILE — скопируй: cp $EXAMPLE $ENVFILE"; exit 1; }

missing=0
keys=$(grep -E '^[A-Z_][A-Z0-9_]*=' "$EXAMPLE" | cut -d= -f1)

for k in $keys; do
  val=$(grep -E "^${k}=" "$ENVFILE" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | xargs)
  case "$val" in
    "" | change_me | CHANGE_ME | ultrasecretkey)
      echo "⚠️  не заполнено/заглушка: $k"
      missing=$((missing + 1)) ;;
  esac
done

if [ "$missing" -eq 0 ]; then
  echo "✅ все ключи из шаблона заполнены"
else
  echo "--- требует внимания: $missing (часть может быть не нужна сейчас, напр. Telethon до шага TG-каналов)"
fi
