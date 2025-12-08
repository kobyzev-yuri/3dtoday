# Конфигурация системы

## 📋 Обзор

Описание параметров конфигурации в файле `config.env`.

## 🔧 Основные настройки

### LLM Provider Configuration

**LLM_PROVIDER** — выбор провайдера LLM:
- `ollama` — локальный Ollama (рекомендуется для разработки)
- `gemini` — Gemini через ProxyAPI.ru (рекомендуется для продакшена)
- `openai` — OpenAI через ProxyAPI.ru

**Автоматический fallback:**
- Система автоматически переключается на доступный провайдер при недоступности основного
- Порядок fallback: ollama → gemini → openai (или в зависимости от настроек)

### OpenAI/ProxyAPI Configuration

```env
OPENAI_API_KEY=your_proxyapi_key_here
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.2
OPENAI_TIMEOUT=600
```

**Использование:** Тот же ключ, что и в sql4A. Используется для:
- Fallback диагностики (если Ollama недоступен)
- Генерации контекста для RAG
- Анализа статей через LLM

### Gemini через ProxyAPI.ru

```env
GEMINI_API_KEY=your_proxyapi_key_here
GEMINI_BASE_URL=https://api.proxyapi.ru/google
GEMINI_MODEL=gemini-3-pro-preview
GEMINI_TEMPERATURE=0.2
GEMINI_TIMEOUT=120
```

**Использование:** Для анализа статей и диагностики через Gemini 3 Pro.

### Ollama Configuration

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_TEMPERATURE=0.2
OLLAMA_TIMEOUT=500
```

**Использование:** Локальный LLM для разработки и тестирования.

## 🗄️ Qdrant Configuration

```env
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=kb_3dtoday
QDRANT_IMAGE_COLLECTION=kb_3dtoday_images
```

**Описание:**
- `QDRANT_HOST` — хост Qdrant сервера
- `QDRANT_PORT` — порт Qdrant сервера
- `QDRANT_COLLECTION` — коллекция для текстовых эмбеддингов
- `QDRANT_IMAGE_COLLECTION` — коллекция для изображений

## 🧠 Embedding Configuration

```env
EMBEDDING_DIMENSION=768
IMAGE_EMBEDDING_DIMENSION=512
HF_MODEL_NAME=intfloat/multilingual-e5-base
```

**Описание:**
- `EMBEDDING_DIMENSION` — размерность текстовых эмбеддингов (768 для multilingual-e5-base)
- `IMAGE_EMBEDDING_DIMENSION` — размерность эмбеддингов изображений (512 для OpenCLIP)
- `HF_MODEL_NAME` — модель эмбеддингов от HuggingFace

## 🖼️ OpenCLIP Configuration

```env
OPENCLIP_MODEL=ViT-B-16
OPENCLIP_PRETRAINED=openai
```

**Описание:**
- `OPENCLIP_MODEL` — модель OpenCLIP для эмбеддингов изображений
- `OPENCLIP_PRETRAINED` — претрейнинг модели

## ⏱️ Timeout Configuration

```env
API_REQUEST_TIMEOUT=300
DIAGNOSTIC_TIMEOUT=300
```

**Описание:**
- `API_REQUEST_TIMEOUT` — таймаут для API запросов (секунды)
- `DIAGNOSTIC_TIMEOUT` — таймаут для диагностики (секунды, может занимать много времени)

## 📊 Logging Configuration

```env
LOG_LEVEL=INFO
LOG_DIR=logs
```

**Описание:**
- `LOG_LEVEL` — уровень логирования (DEBUG, INFO, WARNING, ERROR)
- `LOG_DIR` — директория для логов

## 🔐 Безопасность

**Важно:**
- Файл `config.env` не коммитится в Git (добавлен в `.gitignore`)
- Используйте `config.env.example` как шаблон
- Никогда не коммитьте реальные API ключи

## 📝 Пример полной конфигурации

```env
# LLM Provider
LLM_PROVIDER=gemini

# Gemini через ProxyAPI.ru
GEMINI_API_KEY=your_proxyapi_key_here
GEMINI_BASE_URL=https://api.proxyapi.ru/google
GEMINI_MODEL=gemini-3-pro-preview
GEMINI_TEMPERATURE=0.2
GEMINI_TIMEOUT=120

# OpenAI через ProxyAPI.ru (fallback)
OPENAI_API_KEY=your_proxyapi_key_here
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.2
OPENAI_TIMEOUT=600

# Ollama (локально, опционально)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_TEMPERATURE=0.2
OLLAMA_TIMEOUT=500

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=kb_3dtoday
QDRANT_IMAGE_COLLECTION=kb_3dtoday_images

# Embeddings
EMBEDDING_DIMENSION=768
IMAGE_EMBEDDING_DIMENSION=512
HF_MODEL_NAME=intfloat/multilingual-e5-base

# OpenCLIP
OPENCLIP_MODEL=ViT-B-16
OPENCLIP_PRETRAINED=openai

# Timeouts
API_REQUEST_TIMEOUT=300
DIAGNOSTIC_TIMEOUT=300

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs
```

## 🔄 Изменение конфигурации

После изменения `config.env`:
1. Перезапустите FastAPI сервер
2. Перезапустите Streamlit интерфейсы (если нужно)

## 📚 Дополнительная информация

- Пример конфигурации: см. `config.env.example`
- Подробнее об установке: см. `docs/INSTALLATION.md`
