# Руководство по получению статистики и содержимого KB

## 📊 Способы получения информации о KB

### 1. Через Streamlit интерфейс администратора (самый простой)

**Запуск:**
```bash
streamlit run frontend/admin_ui.py --server.port 8501
```

**Использование:**
1. Откройте http://localhost:8501
2. В боковой панели нажмите кнопку **"🔄 Обновить статистику"**
3. Увидите:
   - Количество статей
   - Количество изображений
   - Всего векторов

**Преимущества:**
- ✅ Визуальный интерфейс
- ✅ Не требует знания API
- ✅ Удобно для быстрой проверки

---

### 2. Через FastAPI endpoint (для программного доступа)

**Endpoint:** `GET /api/kb/statistics`

**Пример запроса:**
```bash
curl http://localhost:8000/api/kb/statistics
```

**Ответ:**
```json
{
  "text_articles": 3,
  "images": 0,
  "total_vectors": 3
}
```

**Пример на Python:**
```python
import httpx

response = httpx.get("http://localhost:8000/api/kb/statistics")
stats = response.json()

print(f"Статей: {stats['text_articles']}")
print(f"Изображений: {stats['images']}")
print(f"Всего векторов: {stats['total_vectors']}")
```

**Преимущества:**
- ✅ Программный доступ
- ✅ Можно использовать в скриптах
- ✅ Интеграция с другими системами

---

### 3. Через MCP инструменты (для агентов)

**Инструмент:** `get_kb_statistics()`

**Пример использования:**
```python
from app.mcp.kb_mcp_server import get_kb_statistics

stats = get_kb_statistics()
print(f"Статей: {stats['text_articles']}")
print(f"Изображений: {stats['images']}")
print(f"Всего векторов: {stats['total_vectors']}")
```

**MCP Resource:** `kb://statistics`

**Пример через MCP клиент:**
```python
# Через MCP сессию
stats = await session.get_resource("kb://statistics")
```

**Преимущества:**
- ✅ Интеграция с MCP агентами
- ✅ Использование в LangGraph/LangChain
- ✅ Доступ через ресурсы MCP

---

### 4. Поиск статей в KB

#### Через API

**Endpoint:** `POST /api/kb/articles/search` (если реализован)

Или через MCP инструмент:

**Инструмент:** `search_kb_articles()`

**Пример:**
```python
from app.mcp.kb_mcp_server import search_kb_articles

# Поиск статей о stringing
results = search_kb_articles(
    query="stringing сопли",
    problem_type="stringing",
    printer_model="Ender-3",
    material="PLA",
    limit=5
)

for article in results['articles']:
    print(f"Заголовок: {article['title']}")
    print(f"Релевантность: {article['relevance_score']}")
    print(f"Контент: {article['content'][:200]}...")
    print("---")
```

**Параметры поиска:**
- `query` - текстовый запрос (обязательно)
- `problem_type` - тип проблемы (опционально)
- `printer_model` - модель принтера (опционально)
- `material` - материал (опционально)
- `limit` - количество результатов (по умолчанию 5)

---

### 5. Получение конкретной статьи

**Инструмент:** `get_article_by_id()`

**Пример:**
```python
from app.mcp.kb_mcp_server import get_article_by_id

article = get_article_by_id("stringing_pla_001")
print(f"Заголовок: {article['title']}")
print(f"Контент: {article['content']}")
print(f"Проблема: {article.get('problem_type')}")
```

---

### 6. Прямое обращение к Qdrant (для продвинутых)

**Пример:**
```python
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)

# Статистика коллекции статей
collection_info = client.get_collection("kb_3dtoday")
print(f"Статей: {collection_info.points_count}")

# Статистика коллекции изображений
image_info = client.get_collection("kb_3dtoday_images")
print(f"Изображений: {image_info.points_count}")

# Поиск статей
results = client.query_points(
    collection_name="kb_3dtoday",
    query_vector=[0.1] * 768,  # Пример вектора
    limit=5
)
```

**Преимущества:**
- ✅ Полный контроль
- ✅ Доступ ко всем функциям Qdrant
- ✅ Продвинутые запросы

---

## 📋 Детальная статистика

### Что включает статистика:

1. **text_articles** - количество текстовых статей
2. **images** - количество изображений
3. **total_vectors** - общее количество векторов
4. **indexed_vectors** - количество проиндексированных векторов

### Дополнительная информация (можно получить через поиск):

- **Покрытие проблем** - какие типы проблем есть в KB
- **Покрытие принтеров** - какие модели принтеров упоминаются
- **Покрытие материалов** - какие материалы описаны
- **Распределение по разделам** - сколько статей в каждом разделе

---

## 🔍 Примеры использования

### Пример 1: Быстрая проверка статистики

```bash
# Через curl
curl http://localhost:8000/api/kb/statistics | python3 -m json.tool
```

### Пример 2: Мониторинг роста KB

```python
import httpx
import time

def monitor_kb_growth(interval=60):
    """Мониторинг роста KB каждые N секунд"""
    prev_count = 0
    
    while True:
        response = httpx.get("http://localhost:8000/api/kb/statistics")
        stats = response.json()
        current_count = stats['text_articles']
        
        if current_count != prev_count:
            print(f"📈 KB выросла: {prev_count} → {current_count} статей")
            prev_count = current_count
        
        time.sleep(interval)

monitor_kb_growth()
```

### Пример 3: Поиск статей по проблеме

```python
from app.mcp.kb_mcp_server import search_kb_articles

# Поиск решений для warping на Ender-3 с PETG
results = search_kb_articles(
    query="warping отслоение углов",
    printer_model="Ender-3",
    material="PETG",
    limit=10
)

print(f"Найдено {results['count']} статей:")
for article in results['articles']:
    print(f"\n📄 {article['title']}")
    print(f"   Релевантность: {article['relevance_score']:.3f}")
    if article.get('solutions'):
        print(f"   Решения: {len(article['solutions'])}")
```

### Пример 4: Анализ покрытия KB

```python
from app.mcp.kb_mcp_server import search_kb_articles

# Проверка покрытия проблем
problems = ["stringing", "warping", "layer_shifting", "under_extrusion"]

for problem in problems:
    results = search_kb_articles(
        query=problem,
        problem_type=problem,
        limit=1
    )
    count = results['count']
    print(f"{problem}: {'✅' if count > 0 else '❌'} ({count} статей)")
```

---

## 🛠️ Утилиты для работы с KB

### Скрипт для проверки статистики

Создайте файл `tools/check_kb_stats.py`:

```python
#!/usr/bin/env python3
"""Скрипт для проверки статистики KB"""

import httpx
import json
import sys

def main():
    try:
        response = httpx.get("http://localhost:8000/api/kb/statistics", timeout=10)
        response.raise_for_status()
        stats = response.json()
        
        print("📊 Статистика базы знаний:")
        print(f"  • Статей: {stats.get('text_articles', 0)}")
        print(f"  • Изображений: {stats.get('images', 0)}")
        print(f"  • Всего векторов: {stats.get('total_vectors', 0)}")
        
        return 0
    except httpx.ConnectError:
        print("❌ Ошибка: FastAPI не запущен")
        print("💡 Запустите: ./scripts/start_fastapi.sh")
        return 1
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

**Использование:**
```bash
python3 tools/check_kb_stats.py
```

---

## 📚 Дополнительная информация

- `backend/app/main.py` - FastAPI endpoints
- `backend/app/mcp/kb_mcp_server.py` - MCP инструменты
- `backend/app/services/vector_db.py` - работа с Qdrant
- `frontend/admin_ui.py` - Streamlit интерфейс

---

## ⚠️ Устранение проблем

### Проблема: "Connection refused"

**Решение:**
```bash
# Запустите FastAPI
./scripts/start_fastapi.sh
```

### Проблема: "Collection not found"

**Решение:**
```bash
# Проверьте, запущен ли Qdrant
docker ps | grep qdrant

# Если нет, запустите
./scripts/start_qdrant.sh
```

### Проблема: Статистика показывает 0

**Возможные причины:**
1. KB пуста (добавьте статьи через интерфейс)
2. Qdrant не запущен
3. Неправильное имя коллекции

**Проверка:**
```python
from app.services.vector_db import get_vector_db

db = get_vector_db()
stats = db.get_statistics()
print(stats)
```


