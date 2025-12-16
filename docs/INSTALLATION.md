# Установка и запуск системы

## 📋 Требования

- Python 3.10+
- Docker и Docker Compose (для Qdrant)
- Ollama (опционально, для локального LLM)
- Git

## 🚀 Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/kobyzev-yuri/3dtoday.git
cd 3dtoday
```

### 2. Установка зависимостей

```bash
cd backend
pip install -r requirements.txt
```

### 3. Настройка конфигурации

Скопируйте `config.env.example` в `config.env` и заполните необходимые параметры:

```bash
cp config.env.example config.env
# Отредактируйте config.env
```

**Основные настройки:**

- **LLM_PROVIDER**: `ollama` (локально), `openai` (ProxyAPI) или `gemini` (ProxyAPI)
  - Система автоматически переключается на доступный провайдер при недоступности основного
  - Порядок fallback: ollama → gemini → openai
- **GEMINI_API_KEY** или **OPENAI_API_KEY**: ключ от ProxyAPI (если используете)
- **OLLAMA_BASE_URL**: URL Ollama (по умолчанию `http://localhost:11434`)

Подробнее: см. `docs/CONFIGURATION.md`

## 🏃 Запуск системы

### Шаг 1: Запуск Qdrant (векторная БД)

**Вариант 1: Через скрипт (рекомендуется)**
```bash
./scripts/start_qdrant.sh
```

**Вариант 2: Через docker-compose**
```bash
docker compose up -d qdrant
```

**Проверка статуса:**
```bash
./scripts/check_services.sh
# или
curl http://localhost:6333/health
```

### Шаг 2: Запуск Ollama (если используется)

```bash
ollama serve
```

Убедитесь, что модель загружена:
```bash
ollama pull qwen3:8b
```

### Шаг 3: Запуск FastAPI Backend

```bash
cd /mnt/ai/cnn/3dtoday
PYTHONPATH=. uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

API будет доступен: `http://localhost:8000`

**Проверка:**
```bash
curl http://localhost:8000/health
# Должен вернуть: {"status":"healthy","version":"0.1.0"}
```

### Шаг 4: Запуск интерфейсов

**Административный интерфейс (управление KB):**
```bash
streamlit run frontend/admin_ui.py
```
Откроется: `http://localhost:8501`

**Пользовательский интерфейс (диагностика):**
```bash
streamlit run frontend/user_ui.py --server.port 8502
```
Откроется: `http://localhost:8502`

## 🔧 Быстрый запуск всех сервисов

Используйте скрипт для запуска всех интерфейсов:

```bash
./scripts/start_interfaces.sh
```

Или вручную в разных терминалах:

```bash
# Терминал 1: Qdrant
./scripts/start_qdrant.sh

# Терминал 2: FastAPI
cd /mnt/ai/cnn/3dtoday
PYTHONPATH=. uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Терминал 3: Admin UI
streamlit run frontend/admin_ui.py

# Терминал 4: User UI
streamlit run frontend/user_ui.py --server.port 8502
```

## ✅ Проверка работы

**Проверка API:**
```bash
curl http://localhost:8000/health
```

**Проверка статистики KB:**
```bash
curl http://localhost:8000/api/kb/statistics
```

**Проверка Qdrant:**
```bash
curl http://localhost:6333/collections
```

## 🐛 Решение проблем

Если возникают проблемы при запуске, см. `docs/TROUBLESHOOTING.md`

## 📚 Следующие шаги

После установки и запуска:

1. **Для администраторов:** см. `docs/KB_MANAGEMENT.md` - как наполнять базу знаний
2. **Для пользователей:** см. `docs/USER_GUIDE.md` - как использовать систему диагностики




