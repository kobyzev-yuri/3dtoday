#!/bin/bash
# Скрипт для проверки статуса сервисов

set -e

echo "🔍 Проверка статуса сервисов..."
echo ""

# Проверка Qdrant
echo "📦 Qdrant:"
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "  ✅ Запущен (http://localhost:6333)"
    if docker ps | grep -q qdrant_3dtoday; then
        echo "  📊 Web UI: http://localhost:6333/dashboard"
    fi
else
    echo "  ❌ Не запущен"
    echo "  💡 Запустите: ./scripts/start_qdrant.sh"
fi

echo ""

# Проверка Ollama
echo "🤖 Ollama:"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "  ✅ Запущен (http://localhost:11434)"
else
    echo "  ❌ Не запущен"
    echo "  💡 Запустите: ollama serve"
fi

echo ""

# Проверка Docker
echo "🐳 Docker:"
if command -v docker &> /dev/null; then
    if docker ps > /dev/null 2>&1; then
        echo "  ✅ Docker доступен"
    else
        echo "  ⚠️  Docker установлен, но не запущен"
    fi
else
    echo "  ❌ Docker не установлен"
fi




