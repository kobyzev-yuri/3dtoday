# Конфигурация проекта 3dtoday

## Обзор

Проект использует конфигурацию и ключи из `../sql4A/config.env` для единообразия и упрощения управления.

## Быстрый старт

### 1. Использование существующей конфигурации

Если у вас уже настроен `../sql4A/config.env`, просто скопируйте ключи:

```bash
# Скопируйте config.env.example
cp config.env.example config.env

# Отредактируйте config.env и используйте ключи из sql4A
# Особенно важно:
# - OPENAI_API_KEY (ProxyAPI ключ)
# - DATABASE_URL (если используется pgvector)
```

### 2. Настройка с нуля

```bash
# 1. Скопируйте пример конфигурации
cp config.env.example config.env

# 2. Отредактируйте config.env
nano config.env

# 3. Заполните обязательные поля:
#    - OPENAI_API_KEY (ProxyAPI ключ)
#    - GEMINI_API_KEY (тот же ProxyAPI ключ)
#    - DATABASE_URL (если используется pgvector)
```

## Структура конфигурации

### LLM Provider

```env
# Выбор провайдера: 'openai' (ProxyAPI), 'ollama', 'gemini'
LLM_PROVIDER=ollama
```

**Варианты:**
- `ollama` — локальные модели (рекомендуется для MVP)
- `openai` — ProxyAPI.ru (GPT-4o)
- `gemini` — Gemini через ProxyAPI.ru

### OpenAI/ProxyAPI (из sql4A)

```env
OPENAI_API_KEY=sk-0rjJ3guVbISwIjvhypozyF4YEicN2fUY
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
OPENAI_MODEL=gpt-4o
```

**Использование:** Тот же ключ, что и в sql4A. Используется для:
- Fallback диагностики (если Ollama недоступен)
- Генерации контекста для RAG

### Gemini через ProxyAPI.ru

```env
GEMINI_API_KEY=sk-0rjJ3guVbISwIjvhypozyF4YEicN2fUY
GEMINI_BASE_URL=https://api.proxyapi.ru/google
GEMINI_MODEL=gemini-3-pro-preview
```

**Использование:** Fallback для анализа изображений дефектов.

**Модели:**
- `gemini-3-pro-preview` — для анализа изображений
- `gemini-3-flash-preview` — более быстрая альтернатива

### Ollama (локальные модели)

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:70b
OLLAMA_VISION_MODEL=llava
```

**Использование:**
- `OLLAMA_MODEL` — для диагностики и диалога
- `OLLAMA_VISION_MODEL` — для анализа изображений дефектов

**Рекомендуемые модели:**
- Диагностика: `llama3.1:70b`, `mistral:7b`, `qwen2.5-coder:1.5b`
- Vision: `llava`, `llava:13b`

### Vector Database

#### Qdrant (рекомендуется)

```env
VECTOR_DB_TYPE=qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=kb_3dtoday
```

**Установка:**
```bash
docker run -d -p 6333:6333 qdrant/qdrant
```

#### pgvector (альтернатива)

```env
VECTOR_DB_TYPE=pgvector
DATABASE_URL=postgresql://postgres:1234@localhost:5432/test_docstructure
VECTOR_TABLE=vanna_vectors
```

**Использование:** Та же БД, что и в sql4A (если используется).

### Embeddings

```env
HF_MODEL_NAME=intfloat/multilingual-e5-base
EMBEDDING_DIMENSION=768
```

**Использование:** Та же модель, что и в sql4A. Поддерживает русский язык.

**Альтернативы:**
- `cointegrated/rubert-tiny2` — легковесная (312d)
- `intfloat/multilingual-e5-large` — более качественная (1024d)

### OpenCLIP (для мультимодальных эмбеддингов)

```env
OPENCLIP_MODEL=ViT-B-16
OPENCLIP_PRETRAINED=openai
```

**Использование:** Эмбеддинги изображений дефектов для MultimodalRAG.

## Загрузка конфигурации в коде

### Python

```python
from dotenv import load_dotenv
from pathlib import Path
import os

# Загружаем config.env из текущего проекта
load_dotenv(dotenv_path=Path(__file__).resolve().parents[0] / "config.env")

# Использование переменных
api_key = os.getenv("OPENAI_API_KEY")
ollama_url = os.getenv("OLLAMA_BASE_URL")
```

### Fallback на sql4A

```python
# Если config.env не найден в текущем проекте, загружаем из sql4A
config_path = Path(__file__).resolve().parents[0] / "config.env"
if not config_path.exists():
    sql4a_config = Path(__file__).resolve().parents[1] / "sql4A" / "config.env"
    if sql4a_config.exists():
        load_dotenv(dotenv_path=sql4a_config)
```

## Переменные окружения

Можно переопределить любую переменную через окружение:

```bash
# Переопределение LLM провайдера
export LLM_PROVIDER=openai

# Переопределение модели
export OLLAMA_MODEL=mistral:7b

# Запуск приложения
python app.py
```

## Проверка конфигурации

```python
# Проверка загрузки конфигурации
import os
from dotenv import load_dotenv

load_dotenv()

print(f"LLM Provider: {os.getenv('LLM_PROVIDER')}")
print(f"Ollama URL: {os.getenv('OLLAMA_BASE_URL')}")
print(f"Qdrant Host: {os.getenv('QDRANT_HOST')}")
print(f"API Key: {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Not set'}")
```

## Безопасность

⚠️ **Важно:**
- Не коммитьте `config.env` в git (добавьте в `.gitignore`)
- Используйте `config.env.example` для примера
- Храните реальные ключи в переменных окружения или секретах

```bash
# .gitignore
config.env
*.env
!config.env.example
```

## Связь с sql4A

Проект использует те же ключи, что и sql4A:
- ✅ **OPENAI_API_KEY** — ProxyAPI ключ (общий)
- ✅ **DATABASE_URL** — та же БД (если используется pgvector)
- ✅ **HF_MODEL_NAME** — та же модель эмбеддингов

Это упрощает:
- Управление ключами (один ключ для всех проектов)
- Использование общей инфраструктуры (БД, Ollama)
- Единообразие конфигурации

## Дополнительные ресурсы

- `../sql4A/config.env` — исходная конфигурация
- `config.env.example` — пример конфигурации
- `RECOMMENDATIONS.md` — детальные рекомендации по архитектуре



