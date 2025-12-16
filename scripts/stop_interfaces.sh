#!/bin/bash
# Скрипт для остановки всех интерфейсов проекта 3dtoday

echo "🛑 Остановка интерфейсов 3dtoday"
echo ""

# Функция для принудительного освобождения порта
free_port() {
    local port=$1
    local pids=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null
        fuser -k $port/tcp 2>/dev/null
        sleep 1
        return 0
    fi
    return 1
}

# Остановка FastAPI
echo "1️⃣ Остановка FastAPI..."
pkill -f "uvicorn.*main:app" 2>/dev/null || true
free_port 8000
if [ $? -eq 0 ]; then
    echo "   ✅ FastAPI остановлен и порт 8000 освобожден"
else
    echo "   ⚠️  FastAPI не запущен"
fi

# Остановка Admin UI
echo "2️⃣ Остановка Admin UI..."
pkill -f "streamlit.*admin_ui" 2>/dev/null || true
free_port 8501
if [ $? -eq 0 ]; then
    echo "   ✅ Admin UI остановлен и порт 8501 освобожден"
else
    echo "   ⚠️  Admin UI не запущен"
fi

# Остановка User UI
echo "3️⃣ Остановка User UI..."
pkill -f "streamlit.*user_ui" 2>/dev/null || true
free_port 8502
if [ $? -eq 0 ]; then
    echo "   ✅ User UI остановлен и порт 8502 освобожден"
else
    echo "   ⚠️  User UI не запущен"
fi

sleep 2

echo ""
echo "✅ Все интерфейсы остановлены"


