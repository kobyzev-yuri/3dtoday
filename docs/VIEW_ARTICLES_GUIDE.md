# Руководство по просмотру статей в KB

## 📋 Способы просмотра статей

### 1. Получить статью по ID (через API)

**Endpoint:** `GET /api/kb/articles/{article_id}`

**Пример:**
```bash
curl http://localhost:8000/api/kb/articles/test_stringing_pla_001
```

**Ответ:**
```json
{
  "article_id": "test_stringing_pla_001",
  "title": "Как устранить stringing (сопли) при печати PLA",
  "content": "Полный текст статьи...",
  "url": "https://3dtoday.ru/...",
  "problem_type": "stringing",
  "printer_models": ["Ender-3"],
  "materials": ["PLA"],
  "symptoms": ["сопли", "нити"],
  "solutions": [...],
  "section": "Техничка",
  "date": "2024-01-01",
  "relevance_score": 1.0
}
```

---

### 2. Список всех статей

**Endpoint:** `GET /api/kb/articles`

**Параметры:**
- `limit` - количество статей (по умолчанию 10)
- `offset` - смещение (по умолчанию 0)

**Примеры:**
```bash
# Первые 10 статей
curl http://localhost:8000/api/kb/articles

# Первые 5 статей
curl http://localhost:8000/api/kb/articles?limit=5

# Статьи с 5 по 10
curl http://localhost:8000/api/kb/articles?limit=5&offset=5
```

**Ответ:**
```json
{
  "articles": [
    {
      "article_id": "test_stringing_pla_001",
      "title": "Как устранить stringing...",
      "url": "https://3dtoday.ru/...",
      "section": "Техничка",
      "problem_type": "stringing",
      "content_preview": "Первые 200 символов..."
    }
  ],
  "total": 3,
  "limit": 10,
  "offset": 0
}
```

---

### 3. Через Swagger UI (интерактивный интерфейс)

**Откройте в браузере:**
```
http://localhost:8000/docs
```

**Использование:**
1. Найдите endpoint `GET /api/kb/articles/{article_id}`
2. Нажмите "Try it out"
3. Введите `article_id` (например, `test_stringing_pla_001`)
4. Нажмите "Execute"
5. Увидите результат

---

### 4. Через Python

**Пример получения статьи:**
```python
import httpx

# Получить статью по ID
response = httpx.get("http://localhost:8000/api/kb/articles/test_stringing_pla_001")
article = response.json()

print(f"Заголовок: {article['title']}")
print(f"Контент: {article['content']}")
print(f"Проблема: {article.get('problem_type')}")
print(f"Принтеры: {article.get('printer_models', [])}")
```

**Пример получения списка:**
```python
import httpx

# Получить список статей
response = httpx.get("http://localhost:8000/api/kb/articles?limit=5")
data = response.json()

print(f"Всего статей: {data['total']}")
for article in data['articles']:
    print(f"\n📄 {article['title']}")
    print(f"   ID: {article['article_id']}")
    print(f"   Раздел: {article.get('section', 'N/A')}")
```

---

### 5. Через MCP инструмент

**Пример:**
```python
from app.mcp.kb_mcp_server import get_article_by_id

article = get_article_by_id("test_stringing_pla_001")
print(f"Заголовок: {article['title']}")
print(f"Контент: {article['content']}")
```

---

## 🔍 Поиск статей

### Поиск по запросу

**Через MCP:**
```python
from app.mcp.kb_mcp_server import search_kb_articles

results = search_kb_articles(
    query="stringing сопли",
    problem_type="stringing",
    printer_model="Ender-3",
    material="PLA",
    limit=5
)

for article in results['articles']:
    print(f"📄 {article['title']}")
    print(f"   Релевантность: {article['relevance_score']}")
```

---

## 📊 Текущие статьи в KB

Для просмотра списка всех статей:

```bash
curl http://localhost:8000/api/kb/articles | python3 -m json.tool
```

Или через Python:
```python
import httpx
import json

response = httpx.get("http://localhost:8000/api/kb/articles")
data = response.json()

print(f"Всего статей: {data['total']}")
for article in data['articles']:
    print(f"\n📄 {article['title']}")
    print(f"   ID: {article['article_id']}")
```

---

## 🛠️ Примеры использования

### Пример 1: Просмотр первой статьи

```bash
# Получить список
curl http://localhost:8000/api/kb/articles?limit=1 | python3 -m json.tool

# Получить первую статью по ID
curl http://localhost:8000/api/kb/articles/test_stringing_pla_001 | python3 -m json.tool
```

### Пример 2: Поиск статей по проблеме

```python
import httpx

# Получить все статьи
response = httpx.get("http://localhost:8000/api/kb/articles?limit=100")
data = response.json()

# Фильтровать по problem_type
stringing_articles = [
    a for a in data['articles'] 
    if a.get('problem_type') == 'stringing'
]

print(f"Найдено статей о stringing: {len(stringing_articles)}")
```

### Пример 3: Экспорт статей

```python
import httpx
import json

response = httpx.get("http://localhost:8000/api/kb/articles?limit=100")
data = response.json()

# Сохранить в файл
with open('kb_articles.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Экспортировано {len(data['articles'])} статей")
```

---

## ⚠️ Устранение проблем

### Проблема: "404 Not Found"

**Причина:** Статья с таким ID не найдена

**Решение:**
1. Проверьте список статей: `curl http://localhost:8000/api/kb/articles`
2. Используйте правильный `article_id` из списка

### Проблема: "Connection refused"

**Причина:** FastAPI не запущен

**Решение:**
```bash
./scripts/start_fastapi.sh
```

---

## 📚 Дополнительная информация

- `backend/app/main.py` - FastAPI endpoints
- `backend/app/mcp/kb_mcp_server.py` - MCP инструменты
- `docs/KB_STATISTICS_GUIDE.md` - статистика KB


