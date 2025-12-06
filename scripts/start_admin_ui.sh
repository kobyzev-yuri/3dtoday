#!/bin/bash
# Скрипт для запуска административного интерфейса

echo "🚀 Запуск административного интерфейса 3dtoday"
echo ""

# Проверка Qdrant
echo "1️⃣ Проверка Qdrant..."
if docker ps | grep -q qdrant; then
    echo "   ✅ Qdrant запущен"
else
    echo "   ⚠️  Qdrant не запущен, запускаю..."
    cd /mnt/ai/cnn/3dtoday
    ./scripts/start_qdrant.sh
    sleep 2
fi

echo ""
echo "2️⃣ Запуск FastAPI Backend..."
echo "   Запустите в отдельном терминале:"
echo "   cd /mnt/ai/cnn/3dtoday"
echo "   uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "   Или запустите автоматически (нажмите Enter для продолжения)..."
read -p ""

# Запуск FastAPI в фоне (опционально)
# uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000 &
# sleep 3

echo ""
echo "3️⃣ Запуск административного интерфейса..."
echo "   URL: http://localhost:8501"
echo ""

cd /mnt/ai/cnn/3dtoday
streamlit run frontend/admin_ui.py


