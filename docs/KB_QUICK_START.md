# Быстрый старт с базой знаний (KB)

## 🚀 Начальная настройка KB

### Вариант 1: С нуля (пустая KB)

1. **Запустите Qdrant:**
   ```bash
   ./scripts/start_qdrant.sh
   ```

2. **Запустите FastAPI:**
   ```bash
   PYTHONPATH=. uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Коллекции создадутся автоматически** при первом обращении к API.

4. **Начните добавлять статьи** через административный интерфейс:
   ```bash
   streamlit run frontend/admin_ui.py
   ```

### Вариант 2: С начальной KB из Git

1. **Найдите последний экспорт KB:**
   ```bash
   ls -lt knowledge_base/export/articles_*.json | head -1
   ```

2. **Запустите Qdrant:**
   ```bash
   ./scripts/start_qdrant.sh
   ```

3. **Импортируйте KB** (если есть скрипт импорта):
   ```bash
   python scripts/import_kb.py knowledge_base/export/articles_YYYYMMDD_HHMMSS.json
   ```

4. **Проверьте импорт:**
   ```bash
   curl http://localhost:8000/api/kb/statistics
   ```

## 📦 Резервное копирование KB

### Экспорт KB в Git

После каждого изменения KB:

```bash
# 1. Экспорт KB
python scripts/export_kb.py

# 2. Добавление в Git
git add knowledge_base/export/*.json

# 3. Коммит
git commit -m "KB backup: $(date +%Y-%m-%d)"

# 4. Отправка в GitHub
git push origin main
```

### Автоматический экспорт (cron)

Добавьте в crontab для еженедельного экспорта:

```bash
0 2 * * 0 cd /path/to/3dtoday && python scripts/export_kb.py && git add knowledge_base/export/*.json && git commit -m "Weekly KB backup" && git push
```

## 📚 Подробная документация

- [KB_BACKUP_AND_RESTORE.md](KB_BACKUP_AND_RESTORE.md) - Полное руководство по резервному копированию
- [KB_MANAGEMENT.md](KB_MANAGEMENT.md) - Управление KB
- [KB_CREATION_FROM_SCRATCH.md](KB_CREATION_FROM_SCRATCH.md) - Создание KB с нуля

