# Решение проблем

## ❌ Ошибка: Connection refused

**Симптомы:**
```
❌ Ошибка подключения к API: [Errno 111] Connection refused
```

**Причина:**
FastAPI сервер не запущен или недоступен на порту 8000.

**Решение:**

1. **Проверьте, запущен ли FastAPI:**
   ```bash
   ps aux | grep uvicorn
   curl http://localhost:8000/health
   ```

2. **Запустите FastAPI:**
   ```bash
   cd /mnt/ai/cnn/3dtoday
   PYTHONPATH=. uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   
   Или используйте скрипт:
   ```bash
   ./scripts/start_fastapi.sh
   ```

3. **Проверьте доступность:**
   ```bash
   curl http://localhost:8000/health
   ```
   
   Должен вернуть: `{"status":"healthy","version":"0.1.0"}`

---

## ❌ Ошибка: ModuleNotFoundError: No module named 'models'

**Симптомы:**
```
ModuleNotFoundError: No module named 'models'
```

**Причина:**
Неправильный путь импорта модулей.

**Решение:**

Запускайте FastAPI с установленным PYTHONPATH:
```bash
cd /mnt/ai/cnn/3dtoday
PYTHONPATH=. uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## ❌ Ошибка: NameError: name 'submitted' is not defined

**Симптомы:**
```
NameError: name 'submitted' is not defined
```

**Причина:**
Переменная используется вне области видимости.

**Решение:**
Исправлено в коде. Убедитесь, что используете последнюю версию `frontend/admin_ui.py`.

---

## ❌ Ошибка: Qdrant connection failed

**Симптомы:**
```
Connection refused to Qdrant
```

**Решение:**

1. **Проверьте Qdrant:**
   ```bash
   docker ps | grep qdrant
   ```

2. **Запустите Qdrant:**
   ```bash
   ./scripts/start_qdrant.sh
   ```

3. **Проверьте подключение:**
   ```bash
   curl http://localhost:6333/collections
   ```

---

## ❌ Ошибка: LLM недоступен

**Симптомы:**
```
Ошибка инициализации LLM
```

**Решение:**

1. **Проверьте Ollama (если используется):**
   ```bash
   ollama list
   curl http://localhost:11434/api/tags
   ```

2. **Проверьте config.env:**
   - Убедитесь, что файл `config.env` существует
   - Проверьте настройки LLM провайдеров

---

## ✅ Чек-лист запуска

Перед использованием интерфейса убедитесь:

- [ ] Qdrant запущен: `docker ps | grep qdrant`
- [ ] FastAPI запущен: `curl http://localhost:8000/health`
- [ ] Streamlit запущен: откройте http://localhost:8501
- [ ] config.env настроен: проверьте наличие файла и ключей

---

## 🔧 Быстрый запуск всех сервисов

```bash
# Терминал 1: Qdrant
./scripts/start_qdrant.sh

# Терминал 2: FastAPI
cd /mnt/ai/cnn/3dtoday
PYTHONPATH=. uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Терминал 3: Streamlit Admin UI
streamlit run frontend/admin_ui.py

# Терминал 4: Streamlit User UI (опционально)
streamlit run frontend/user_ui.py --server.port 8502
```

---

## 📚 Дополнительная информация

- `README.md` - общая информация о проекте
- `QUICK_START.md` - быстрый старт
- `docs/STREAMLIT_INTERFACES_GUIDE.md` - руководство по интерфейсам


