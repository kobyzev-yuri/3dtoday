# Анализ возможности переиспользования кода из sql4A

## 📊 Обзор архитектуры sql4A

### Основные компоненты:

1. **FastAPI сервер** (`src/api/main.py`)
   - REST API для генерации SQL
   - Endpoints для обучения KB (`/training/*`)
   - Health check, тестирование поиска

2. **QueryService** (`src/services/query_service.py`)
   - Генерация SQL через LLM (OpenAI/Ollama)
   - RAG pipeline с семантическим поиском
   - Работа с векторной БД (pgvector)

3. **Vanna модули** (`src/vanna/`)
   - `vanna_pgvector_native.py` - работа с pgvector
   - `vanna_semantic_fixed.py` - семантический поиск
   - Поддержка DDL, Documentation, Q/A Examples

4. **Модели данных** (`src/models/`)
   - Pydantic модели для запросов/ответов
   - Валидация данных

---

## ✅ Что МОЖНО переиспользовать

### 1. **Архитектура FastAPI сервиса** ⭐⭐⭐⭐⭐

**Файлы:**
- `src/api/main.py` - структура API
- `src/models/requests.py` - модели запросов
- `src/models/responses.py` - модели ответов

**Что использовать:**
- ✅ Структура endpoints для KB (`/training/*`)
- ✅ Health check endpoint
- ✅ Обработка ошибок
- ✅ CORS middleware
- ✅ Логирование

**Адаптация:**
- Заменить SQL генерацию на диагностику 3D-печати
- Адаптировать endpoints под домен 3D-печати

**Пример адаптации:**
```python
# Было (sql4A):
@app.post("/query", response_model=SQLResponse)
async def generate_sql(request: QueryRequest):
    sql = await query_service.generate_sql(...)
    return SQLResponse(sql=sql, ...)

# Станет (3dtoday):
@app.post("/diagnose", response_model=DiagnosticResponse)
async def diagnose_problem(request: DiagnosticRequest):
    diagnosis = await diagnostic_service.diagnose(...)
    return DiagnosticResponse(diagnosis=diagnosis, ...)
```

### 2. **Структура QueryService** ⭐⭐⭐⭐

**Файл:** `src/services/query_service.py`

**Что использовать:**
- ✅ Инициализация сервисов
- ✅ RAG pipeline (метод `_get_rag_context`)
- ✅ Работа с векторной БД
- ✅ Гибридный поиск (семантический + фильтры)

**Адаптация:**
- Заменить `generate_sql` на `diagnose_problem`
- Адаптировать RAG под статьи 3D-печати
- Изменить метаданные фильтрации

**Пример:**
```python
# Было (sql4A):
async def generate_sql(self, question: str, user_context: Dict):
    rag_context = await self._get_rag_context(question, domain)
    sql = await self.pipeline.generate_sql(...)
    return sql

# Станет (3dtoday):
async def diagnose_problem(self, user_input: str, image: Optional[bytes], context: Dict):
    # Анализ изображения (если есть)
    if image:
        vision_result = await self.vision_agent.analyze(image)
        user_input += f" {vision_result}"
    
    # RAG поиск статей
    rag_context = await self._get_rag_context(user_input, context)
    
    # Диагностика
    diagnosis = await self.diagnostic_agent.diagnose(user_input, rag_context, context)
    return diagnosis
```

### 3. **Работа с векторной БД** ⭐⭐⭐⭐⭐

**Файл:** `src/vanna/vanna_pgvector_native.py`

**Что использовать:**
- ✅ Методы `add_ddl`, `add_documentation`, `add_question_sql`
- ✅ Структура метаданных в JSON
- ✅ Семантический поиск

**Адаптация:**
- Переименовать методы под статьи:
  - `add_ddl` → `add_article_structure`
  - `add_documentation` → `add_article_content`
  - `add_question_sql` → `add_diagnostic_example`

**Пример адаптации:**
```python
# Было (sql4A):
def add_question_sql(self, question: str, sql: str, **kwargs):
    metadata = {
        'type': 'question_sql',
        'question': question,
        'sql': sql,
        'domain': kwargs.get('domain'),
        'tags': kwargs.get('tags', [])
    }
    # ... добавление в БД

# Станет (3dtoday):
def add_diagnostic_example(self, problem: str, solution: Dict, **kwargs):
    metadata = {
        'type': 'diagnostic_example',
        'problem': problem,
        'solution': solution,
        'problem_type': kwargs.get('problem_type'),
        'printer_models': kwargs.get('printer_models', []),
        'materials': kwargs.get('materials', []),
        'tags': kwargs.get('tags', [])
    }
    # ... добавление в БД
```

### 4. **Модели данных (Pydantic)** ⭐⭐⭐⭐

**Файлы:**
- `src/models/requests.py`
- `src/models/responses.py`

**Что использовать:**
- ✅ Структура моделей
- ✅ Валидация полей
- ✅ Типизация

**Адаптация:**
- Создать новые модели для диагностики:
  - `DiagnosticRequest` вместо `QueryRequest`
  - `DiagnosticResponse` вместо `SQLResponse`
  - `ArticleRequest` вместо `TrainingDDLRequest`

**Пример:**
```python
# Было (sql4A):
class QueryRequest(BaseModel):
    question: str
    user_id: str
    role: str
    context: Optional[Dict[str, Any]]

# Станет (3dtoday):
class DiagnosticRequest(BaseModel):
    user_input: str
    image: Optional[bytes] = None
    printer_model: Optional[str] = None
    material: Optional[str] = None
    session_id: str
    context: Optional[Dict[str, Any]] = None
```

### 5. **RAG Pipeline** ⭐⭐⭐⭐⭐

**Что использовать:**
- ✅ Метод `_get_rag_context` из QueryService
- ✅ Гибридный поиск (семантический + фильтры)
- ✅ Формирование контекста для LLM

**Адаптация:**
- Изменить фильтры метаданных:
  - Вместо `domain` → `problem_type`, `printer_model`, `material`
  - Вместо SQL примеров → статьи и диагностические примеры

---

## ⚠️ Что нужно АДАПТИРОВАТЬ

### 1. **Домен-специфичная логика**

**SQL генерация → Диагностика:**
- ❌ Генерация SQL запросов
- ✅ Диагностика проблем 3D-печати
- ✅ Формулировка уточняющих вопросов
- ✅ Пошаговые инструкции

**Адаптация:**
```python
# Заменить SQL генератор на диагностический агент
# Было:
self.pipeline = create_simple_sql_generator(config)

# Станет:
self.diagnostic_agent = create_diagnostic_agent(config)
self.vision_agent = create_vision_agent(config)
```

### 2. **Метаданные**

**SQL метаданные → 3D-печать метаданные:**
- ❌ `table_name`, `domain`, `sql`
- ✅ `problem_type`, `printer_models`, `materials`, `symptoms`

**Адаптация:**
```python
# Было:
metadata = {
    'type': 'question_sql',
    'domain': 'payments',
    'table': 'tbl_incoming_payments'
}

# Станет:
metadata = {
    'type': 'diagnostic_example',
    'problem_type': 'stringing',
    'printer_models': ['Ender-3', 'Ender-3 V2'],
    'materials': ['PLA'],
    'symptoms': ['ниточки', 'сопли']
}
```

### 3. **Векторная БД**

**pgvector → Qdrant:**
- ⚠️ sql4A использует pgvector (PostgreSQL)
- ✅ Рекомендация для 3dtoday: Qdrant (из RECOMMENDATIONS.md)

**Варианты:**
1. **Адаптировать под Qdrant** (рекомендуется)
   - Использовать `qdrant-client` вместо pgvector
   - Адаптировать методы поиска

2. **Использовать pgvector** (если уже есть PostgreSQL)
   - Переиспользовать код как есть
   - Но Qdrant проще для нового проекта

**Пример адаптации под Qdrant:**
```python
# Было (pgvector):
async def search(self, query: str, limit: int = 5):
    conn = await asyncpg.connect(self.database_url)
    results = await conn.fetch("""
        SELECT content, metadata, embedding <-> $1::vector as distance
        FROM vanna_vectors
        WHERE content_type = 'question_sql'
        ORDER BY embedding <-> $1::vector
        LIMIT $2
    """, query_embedding, limit)

# Станет (Qdrant):
async def search(self, query: str, limit: int = 5):
    query_embedding = self.embedding_model.encode(query)
    results = self.qdrant_client.search(
        collection_name="kb_3dtoday",
        query_vector=query_embedding.tolist(),
        query_filter={
            "must": [
                {"key": "type", "match": {"value": "diagnostic_example"}}
            ]
        },
        limit=limit
    )
```

### 4. **Мультимодальность**

**Добавить:**
- ✅ Анализ изображений (Vision Agent)
- ✅ Интеграция анализа фото в RAG контекст
- ✅ Мультимодальные эмбеддинги

**Новый код:**
```python
class VisionAgent:
    async def analyze_image(self, image: bytes) -> Dict:
        # Анализ через llava (Ollama)
        result = await self.ollama_client.generate(
            model="llava",
            prompt=f"Опиши дефект на этом изображении 3D-печати: {image}",
            images=[image]
        )
        return {
            "problem_type": self._extract_problem_type(result),
            "symptoms": self._extract_symptoms(result),
            "description": result
        }
```

---

## 🎯 Рекомендации по переиспользованию

### ✅ **ИСПОЛЬЗОВАТЬ (с минимальной адаптацией):**

1. **FastAPI структура** - 90% переиспользования
   - Endpoints, middleware, обработка ошибок
   - Модели запросов/ответов (адаптировать поля)

2. **QueryService архитектура** - 70% переиспользования
   - RAG pipeline
   - Гибридный поиск
   - Инициализация сервисов

3. **Работа с векторной БД** - 60% переиспользования
   - Методы добавления данных
   - Структура метаданных (адаптировать поля)
   - ⚠️ Нужна адаптация под Qdrant

### ⚠️ **АДАПТИРОВАТЬ:**

1. **Домен-специфичная логика** - 30% переиспользования
   - SQL генерация → Диагностика
   - Добавить Vision Agent
   - Изменить промпты для LLM

2. **Метаданные** - 40% переиспользования
   - Адаптировать поля под 3D-печать
   - Добавить новые поля (printer_models, materials, symptoms)

3. **Векторная БД** - 50% переиспользования
   - Адаптация под Qdrant (если выбран)
   - Или использовать pgvector как есть

### ❌ **НЕ ИСПОЛЬЗОВАТЬ:**

1. **SQL-специфичные компоненты**
   - SQL генераторы (OpenAI/Ollama SQL)
   - EXPLAIN PLAN валидация
   - Оптимизация SQL запросов

2. **Ролевые ограничения SQL**
   - Mock API для SQL execution
   - Ролевые фильтры SQL

---

## 📋 План адаптации

### Этап 1: Базовая структура (1-2 дня)

1. **Скопировать структуру FastAPI:**
   ```bash
   # Из sql4A:
   - src/api/main.py → backend/app/main.py
   - src/models/ → backend/app/models/
   - src/services/query_service.py → backend/app/services/diagnostic_service.py
   ```

2. **Адаптировать модели:**
   - `QueryRequest` → `DiagnosticRequest`
   - `SQLResponse` → `DiagnosticResponse`
   - `TrainingExampleRequest` → `DiagnosticExampleRequest`

3. **Адаптировать endpoints:**
   - `/query` → `/diagnose`
   - `/training/example` → `/training/diagnostic_example`
   - `/training/ddl` → `/training/article`
   - `/training/documentation` → `/training/article_content`

### Этап 2: RAG Pipeline (2-3 дня)

1. **Адаптировать QueryService:**
   - Переименовать в `DiagnosticService`
   - Заменить SQL генерацию на диагностику
   - Адаптировать RAG под статьи 3D-печати

2. **Адаптировать метаданные:**
   - Изменить фильтры поиска
   - Добавить новые поля метаданных

3. **Интегрировать Vision Agent:**
   - Добавить анализ изображений
   - Интегрировать в RAG контекст

### Этап 3: Векторная БД (2-3 дня)

1. **Выбрать БД:**
   - Qdrant (рекомендуется) или pgvector

2. **Адаптировать методы:**
   - `add_ddl` → `add_article_structure`
   - `add_documentation` → `add_article_content`
   - `add_question_sql` → `add_diagnostic_example`

3. **Адаптировать поиск:**
   - Изменить фильтры метаданных
   - Адаптировать под выбранную БД

### Этап 4: Тестирование (1-2 дня)

1. **Протестировать endpoints**
2. **Проверить RAG pipeline**
3. **Валидировать метаданные**

---

## 💡 Конкретные примеры кода

### Пример 1: Адаптация endpoint

```python
# Было (sql4A):
@app.post("/query", response_model=SQLResponse)
async def generate_sql(request: QueryRequest):
    sql = await query_service.generate_sql(
        question=request.question,
        user_context={
            "user_id": request.user_id,
            "role": request.role
        }
    )
    return SQLResponse(sql=sql, question=request.question, user_id=request.user_id)

# Станет (3dtoday):
@app.post("/diagnose", response_model=DiagnosticResponse)
async def diagnose_problem(request: DiagnosticRequest):
    diagnosis = await diagnostic_service.diagnose(
        user_input=request.user_input,
        image=request.image,
        context={
            "printer_model": request.printer_model,
            "material": request.material,
            "session_id": request.session_id
        }
    )
    return DiagnosticResponse(
        diagnosis=diagnosis,
        user_input=request.user_input,
        session_id=request.session_id
    )
```

### Пример 2: Адаптация RAG поиска

```python
# Было (sql4A):
async def _get_rag_context(self, question: str, domain: str) -> str:
    results = await self.semantic_vanna.get_similar_question_sql(
        question, 
        limit=5,
        filters={'domain': domain}
    )
    return "\n\n".join(results)

# Станет (3dtoday):
async def _get_rag_context(self, user_input: str, context: Dict) -> str:
    # Поиск статей с фильтрацией по метаданным
    results = await self.vector_db.search(
        query=user_input,
        filters={
            "problem_type": context.get("problem_type"),
            "printer_models": context.get("printer_model"),
            "materials": context.get("material")
        },
        limit=5
    )
    
    # Формирование контекста из статей
    context_parts = []
    for article in results:
        context_parts.append(f"Статья: {article['title']}\n{article['content']}")
    
    return "\n\n".join(context_parts)
```

### Пример 3: Адаптация добавления данных

```python
# Было (sql4A):
def add_question_sql(self, question: str, sql: str, **kwargs):
    metadata = {
        'type': 'question_sql',
        'question': question,
        'sql': sql,
        'domain': kwargs.get('domain'),
        'tags': kwargs.get('tags', [])
    }
    # ... добавление в pgvector

# Станет (3dtoday):
def add_diagnostic_example(self, problem: str, solution: Dict, **kwargs):
    metadata = {
        'type': 'diagnostic_example',
        'problem': problem,
        'solution': solution,
        'problem_type': kwargs.get('problem_type'),
        'printer_models': kwargs.get('printer_models', []),
        'materials': kwargs.get('materials', []),
        'symptoms': kwargs.get('symptoms', []),
        'tags': kwargs.get('tags', [])
    }
    # ... добавление в Qdrant
```

---

## ✅ Итоговые рекомендации

### ✅ **ИСПОЛЬЗОВАТЬ код sql4A:**

1. **FastAPI структура** - переиспользовать 90%
2. **RAG pipeline** - переиспользовать 70%
3. **Модели данных** - переиспользовать 60% (адаптировать поля)
4. **Работа с векторной БД** - переиспользовать 60% (адаптировать под Qdrant)

### ⚠️ **АДАПТИРОВАТЬ:**

1. **Домен-специфичная логика** - SQL → Диагностика
2. **Метаданные** - адаптировать под 3D-печать
3. **Векторная БД** - адаптировать под Qdrant (или использовать pgvector)

### ❌ **НЕ ИСПОЛЬЗОВАТЬ:**

1. SQL генераторы
2. EXPLAIN PLAN валидация
3. Ролевые ограничения SQL

---

## 🎯 Вывод

**Можно переиспользовать ~70% кода из sql4A** с адаптацией:

- ✅ **Архитектура FastAPI** - готова к использованию
- ✅ **RAG pipeline** - требует минимальной адаптации
- ✅ **Структура сервисов** - готова к использованию
- ⚠️ **Домен-специфичная логика** - требует полной переработки
- ⚠️ **Векторная БД** - требует адаптации под Qdrant

**Рекомендация:** Использовать sql4A как основу, адаптировать под домен 3D-печати. Это сэкономит ~2-3 недели разработки.




