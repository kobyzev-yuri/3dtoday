#!/bin/bash
# Скрипт для остановки всех интерфейсов проекта 3dtoday

echo "🛑 Остановка интерфейсов 3dtoday"
echo ""

# Остановка FastAPI
echo "1️⃣ Остановка FastAPI..."
if pkill -f "uvicorn.*main:app" 2>/dev/null; then
    echo "   ✅ FastAPI остановлен"
else
    echo "   ⚠️  FastAPI не запущен"
fi

# Остановка Admin UI
echo "2️⃣ Остановка Admin UI..."
if pkill -f "streamlit.*admin_ui" 2>/dev/null; then
    echo "   ✅ Admin UI остановлен"
else
    echo "   ⚠️  Admin UI не запущен"
fi

# Остановка User UI
echo "3️⃣ Остановка User UI..."
if pkill -f "streamlit.*user_ui" 2>/dev/null; then
    echo "   ✅ User UI остановлен"
else
    echo "   ⚠️  User UI не запущен"
fi

sleep 2

echo ""
echo "✅ Все интерфейсы остановлены"

