#!/bin/bash
# Скрипт для запуска FastAPI сервера

echo "🚀 Запуск FastAPI сервера для проекта 3dtoday"
echo ""

cd /mnt/ai/cnn/3dtoday

# Проверка Qdrant
echo "1️⃣ Проверка Qdrant..."
if docker ps | grep -q qdrant; then
    echo "   ✅ Qdrant запущен"
else
    echo "   ⚠️  Qdrant не запущен, запускаю..."
    ./scripts/start_qdrant.sh
    sleep 2
fi

echo ""
echo "2️⃣ Запуск FastAPI на http://localhost:8000"
echo ""

# Запуск FastAPI
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000



