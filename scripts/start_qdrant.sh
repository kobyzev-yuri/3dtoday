#!/bin/bash
# Скрипт для запуска Qdrant в Docker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🚀 Запуск Qdrant в Docker..."

# Проверка наличия Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не найден. Установите Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Проверка, запущен ли уже Qdrant
if docker ps | grep -q qdrant_3dtoday; then
    echo "✅ Qdrant уже запущен"
    docker ps | grep qdrant_3dtoday
    exit 0
fi

# Запуск через docker compose (новая версия) или docker-compose (старая)
if command -v docker &> /dev/null && docker compose version &> /dev/null 2>&1; then
    docker compose up -d qdrant
elif command -v docker-compose &> /dev/null; then
    docker-compose up -d qdrant
else
    echo "❌ docker compose не найден"
    exit 1
fi

# Ожидание запуска
echo "⏳ Ожидание запуска Qdrant..."
sleep 5

# Проверка доступности
for i in {1..10}; do
    if curl -s http://localhost:6333/health > /dev/null 2>&1; then
        echo "✅ Qdrant успешно запущен и доступен на http://localhost:6333"
        echo "📊 Web UI: http://localhost:6333/dashboard"
        exit 0
    fi
    sleep 2
done

echo "⚠️  Qdrant запущен, но не отвечает. Проверьте логи: docker logs qdrant_3dtoday"
exit 1

