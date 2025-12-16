#!/bin/bash
# Скрипт для тестирования URL с изображениями в KB
# Проверяет доступность API и запускает тесты

set -e

API_URL="http://localhost:8000"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "======================================================================"
echo "🧪 Тест: Загрузка URL с изображениями в KB"
echo "======================================================================"
echo ""

# Проверка доступности API
echo "📋 ШАГ 1: Проверка доступности API..."
if curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
    echo "✅ API сервер доступен на ${API_URL}"
else
    echo "❌ API сервер недоступен на ${API_URL}"
    echo ""
    echo "Запустите сервер командой:"
    echo "  cd $PROJECT_ROOT && PYTHONPATH=. uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload"
    echo ""
    exit 1
fi

echo ""

# Проверка аргументов
if [ $# -eq 0 ]; then
    echo "Использование: $0 <URL> [provider]"
    echo ""
    echo "Примеры:"
    echo "  $0 'https://www.simplify3d.com/resources/print-quality-troubleshooting/stringing-or-oozing/' gemini"
    echo "  $0 'https://all3dp.com/2/3d-printing-warping-how-to-fix-it/' gemini"
    echo ""
    echo "Провайдеры: gemini (по умолчанию), openai, ollama"
    exit 1
fi

URL="$1"
PROVIDER="${2:-gemini}"

echo "📋 ШАГ 2: Запуск теста..."
echo "URL: $URL"
echo "Провайдер: $PROVIDER"
echo ""

# Переход в директорию проекта
cd "$PROJECT_ROOT"

# Запуск теста
python3 "$SCRIPT_DIR/test_url_with_images.py" "$URL" --provider "$PROVIDER"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "======================================================================"
    echo "✅ Тест завершен успешно!"
    echo "======================================================================"
else
    echo "======================================================================"
    echo "❌ Тест завершен с ошибками (код: $EXIT_CODE)"
    echo "======================================================================"
fi

exit $EXIT_CODE


