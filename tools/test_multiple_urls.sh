#!/bin/bash
# Скрипт для тестирования нескольких URL с изображениями из image_urls.json

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_URL="http://localhost:8000"

echo "======================================================================"
echo "🧪 Тест: Загрузка нескольких URL с изображениями в KB"
echo "======================================================================"
echo ""

# Проверка доступности API
echo "📋 Проверка доступности API..."
if curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
    echo "✅ API сервер доступен"
else
    echo "❌ API сервер недоступен на ${API_URL}"
    echo ""
    echo "Запустите сервер командой:"
    echo "  cd $PROJECT_ROOT && PYTHONPATH=. uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload"
    exit 1
fi

echo ""

# Извлечение URL из image_urls.json
URLS_FILE="$PROJECT_ROOT/knowledge_base/image_urls.json"

if [ ! -f "$URLS_FILE" ]; then
    echo "❌ Файл $URLS_FILE не найден"
    exit 1
fi

# Извлекаем URL из JSON (приоритетные источники)
echo "📋 Извлечение URL из $URLS_FILE..."
URLS=$(python3 -c "
import json
import sys

with open('$URLS_FILE', 'r', encoding='utf-8') as f:
    data = json.load(f)

urls = []
# Приоритетные источники
for category in ['priority_high', 'priority_medium']:
    if category in data:
        for problem_type, articles in data[category].items():
            for article in articles:
                if article.get('has_images', False):
                    urls.append(article['url'])

# Выводим первые 5 URL для тестирования
for url in urls[:5]:
    print(url)
" 2>/dev/null)

if [ -z "$URLS" ]; then
    echo "❌ Не удалось извлечь URL из $URLS_FILE"
    exit 1
fi

echo "✅ Найдено URL для тестирования:"
echo "$URLS" | nl
echo ""

# Спрашиваем подтверждение
read -p "Продолжить тестирование? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Отменено"
    exit 0
fi

echo ""
echo "======================================================================"
echo "🚀 Начало тестирования"
echo "======================================================================"
echo ""

SUCCESS=0
FAILED=0
TOTAL=0

cd "$PROJECT_ROOT"

# Тестируем каждый URL
while IFS= read -r URL; do
    if [ -z "$URL" ]; then
        continue
    fi
    
    TOTAL=$((TOTAL + 1))
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Тест $TOTAL: $URL"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    if python3 "$SCRIPT_DIR/test_url_with_images.py" "$URL" --provider gemini; then
        SUCCESS=$((SUCCESS + 1))
        echo "✅ Тест $TOTAL успешен"
    else
        FAILED=$((FAILED + 1))
        echo "❌ Тест $TOTAL провален"
    fi
    
    # Небольшая пауза между тестами
    sleep 2
    
done <<< "$URLS"

echo ""
echo "======================================================================"
echo "📊 Результаты тестирования"
echo "======================================================================"
echo "Всего тестов: $TOTAL"
echo "Успешно: $SUCCESS"
echo "Провалено: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ Все тесты прошли успешно!"
    exit 0
else
    echo "⚠️  Некоторые тесты провалились"
    exit 1
fi


