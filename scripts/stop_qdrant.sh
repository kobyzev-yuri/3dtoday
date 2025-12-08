#!/bin/bash
# Скрипт для остановки Qdrant

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🛑 Остановка Qdrant..."

if command -v docker-compose &> /dev/null; then
    docker-compose stop qdrant
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    docker compose stop qdrant
else
    echo "❌ docker-compose не найден"
    exit 1
fi

echo "✅ Qdrant остановлен"




