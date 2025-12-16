#!/bin/bash
# Скрипт для запуска всех интерфейсов проекта 3dtoday

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "🚀 Запуск системы 3dtoday"
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

# Функция для остановки процессов
stop_interfaces() {
    echo "🛑 Остановка интерфейсов..."
    pkill -f "uvicorn.*main:app" 2>/dev/null || true
    pkill -f "streamlit.*admin_ui" 2>/dev/null || true
    pkill -f "streamlit.*user_ui" 2>/dev/null || true
    free_port 8000 || true
    free_port 8501 || true
    free_port 8502 || true
    sleep 2
    echo "✅ Процессы остановлены"
}

# Функция для проверки порта
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0
    else
        return 1
    fi
}

# Остановка существующих процессов
stop_interfaces

# Проверка Qdrant
echo "1️⃣ Проверка Qdrant..."
if docker ps | grep -q qdrant; then
    echo "   ✅ Qdrant запущен"
else
    echo "   ⚠️  Qdrant не запущен, запускаю..."
    ./scripts/start_qdrant.sh
    sleep 3
fi

echo ""

# Запуск FastAPI Backend
echo "2️⃣ Запуск FastAPI Backend на http://localhost:8000"
if check_port 8000; then
    echo "   ⚠️  Порт 8000 уже занят, освобождаю..."
    free_port 8000
    sleep 2
fi
cd "$PROJECT_DIR"
nohup uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000 > logs/fastapi.log 2>&1 &
FASTAPI_PID=$!
echo "   ✅ FastAPI запущен (PID: $FASTAPI_PID)"
echo "   Логи: logs/fastapi.log"
sleep 3

echo ""

# Запуск административного интерфейса
echo "3️⃣ Запуск административного интерфейса на http://localhost:8501"
if check_port 8501; then
    echo "   ⚠️  Порт 8501 уже занят, освобождаю..."
    free_port 8501
    sleep 2
fi
cd "$PROJECT_DIR"
nohup streamlit run frontend/admin_ui.py --server.port 8501 > logs/admin_ui.log 2>&1 &
ADMIN_UI_PID=$!
echo "   ✅ Admin UI запущен (PID: $ADMIN_UI_PID)"
echo "   Логи: logs/admin_ui.log"
sleep 3

echo ""

# Запуск пользовательского интерфейса
echo "4️⃣ Запуск пользовательского интерфейса на http://localhost:8502"
if check_port 8502; then
    echo "   ⚠️  Порт 8502 уже занят, освобождаю..."
    free_port 8502
    sleep 2
fi
cd "$PROJECT_DIR"
nohup streamlit run frontend/user_ui.py --server.port 8502 > logs/user_ui.log 2>&1 &
USER_UI_PID=$!
echo "   ✅ User UI запущен (PID: $USER_UI_PID)"
echo "   Логи: logs/user_ui.log"
sleep 2

echo ""
echo "✅ Все интерфейсы запущены!"
echo ""
echo "📋 Доступные интерфейсы:"
echo "   - FastAPI: http://localhost:8000"
echo "   - Admin UI: http://localhost:8501"
echo "   - User UI: http://localhost:8502"
echo ""
echo "📁 Логи:"
echo "   - FastAPI: logs/fastapi.log"
echo "   - Admin UI: logs/admin_ui.log"
echo "   - User UI: logs/user_ui.log"
echo ""
echo "🛑 Для остановки используйте: ./scripts/stop_interfaces.sh"


