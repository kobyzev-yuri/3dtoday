# Быстрое тестирование загрузки документов

## 🚀 Быстрый старт

### Шаг 1: Убедитесь, что API запущен

```bash
curl http://localhost:8000/health
```

Если не запущен:
```bash
cd /mnt/ai/cnn/3dtoday
PYTHONPATH=. uvicorn backend.app.main:app --reload
```

### Шаг 2: Запустите тесты ВСЕХ ТРЕХ ФАЗ

**⚠️ ВАЖНО: Процесс состоит из трех фаз:**
1. **Парсинг** - извлечение контента
2. **Анализ релевантности** - проверка через библиотекаря
3. **Размещение в KB** - индексация

**Вариант A: Тест всех провайдеров (РЕКОМЕНДУЕТСЯ) ⭐**
```bash
# Все варианты: Ollama (упрощенный), Gemini (с изображениями), OpenAI
python tools/test_all_providers.py --all

# Только Gemini с анализом изображений (самый важный)
python tools/test_all_providers.py --gemini --url "https://www.simplify3d.com/resources/print-quality-troubleshooting/stringing-or-oozing/"

# Только Ollama (упрощенный, для ограниченных ресурсов)
python tools/test_all_providers.py --ollama

# Тест фильтрации нерелевантного контента
python tools/test_all_providers.py --filtering
```

**Вариант B: Полный тест всех трех фаз**
```bash
# Релевантная статья (Simplify3D Stringing)
python tools/test_full_workflow.py --url "https://www.simplify3d.com/resources/print-quality-troubleshooting/stringing-or-oozing/"

# Тест отклонения нерелевантной статьи
python tools/test_full_workflow.py --rejection-only

# Тест ручного ввода
python tools/test_full_workflow.py --manual-only
```

**Вариант C: Через административный интерфейс (рекомендуется)**
```bash
streamlit run frontend/admin_ui.py
```

---

## 📋 Что протестировать ПРЯМО СЕЙЧАС

### 1. URL через LLM (Simplify3D Stringing) ⭐ ПРИОРИТЕТ

**Через curl:**
```bash
curl -X POST "http://localhost:8000/api/kb/articles/parse_with_llm" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.simplify3d.com/resources/print-quality-troubleshooting/stringing-or-oozing/",
    "llm_provider": "gemini",
    "model": "gemini-3-pro-preview"
  }' | jq '.'
```

**Через административный интерфейс:**
1. Откройте `http://localhost:8501`
2. Выберите "🤖 По URL (через LLM - GPT-4o/Gemini)"
3. Вставьте URL: `https://www.simplify3d.com/resources/print-quality-troubleshooting/stringing-or-oozing/`
4. Выберите провайдер: Gemini
5. Нажмите "🤖 Анализировать через LLM"

**Что проверить:**
- ✅ Статья распарсена
- ✅ Извлечены изображения (3-5 штук)
- ✅ Метаданные: problem_type=stringing
- ✅ Релевантность > 0.7

---

### 2. Ручной ввод (JSON)

**Через curl:**
```bash
curl -X POST "http://localhost:8000/api/kb/articles/add" \
  -H "Content-Type: application/json" \
  -d @tools/test_data/sample_article.json | jq '.'
```

**Через административный интерфейс:**
1. Выберите "📝 Ручной ввод"
2. Заполните форму или используйте данные из `tools/test_data/sample_article.json`

---

### 3. URL обычный парсинг

```bash
curl -X POST "http://localhost:8000/api/kb/articles/parse" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "https://all3dp.com/2/3d-printing-warping-how-to-fix-it/",
    "source_type": "url",
    "llm_provider": "ollama"
  }' | jq '.'
```

---

## 🎯 Рекомендуемый порядок тестирования

1. **Simplify3D Stringing через LLM** - лучший пример с изображениями
2. **Ручной ввод** - простой тест базовой функциональности
3. **All3DP Warping** - обычный парсинг URL
4. **Файлы (TXT/MD)** - если нужно протестировать парсинг файлов

---

## 📊 Чек-лист

Для каждого теста проверьте:

- [ ] Парсинг работает
- [ ] Метаданные извлечены (problem_type, materials)
- [ ] Релевантность > 0.7
- [ ] Изображения извлечены (если есть)
- [ ] Статья может быть добавлена в KB

---

## 🔗 Полезные URL для тестирования

**Из `knowledge_base/image_urls.json`:**

1. **Stringing:**
   - Simplify3D: https://www.simplify3d.com/resources/print-quality-troubleshooting/stringing-or-oozing/
   - All3DP: https://all3dp.com/2/3d-print-stringing-how-to-fix-it/
   - Prusa: https://help.prusa3d.com/article/stringing-or-oozing_1256

2. **Warping:**
   - Simplify3D: https://www.simplify3d.com/resources/print-quality-troubleshooting/warping/
   - All3DP: https://all3dp.com/2/3d-printing-warping-how-to-fix-it/

3. **Layer Separation:**
   - Simplify3D: https://www.simplify3d.com/resources/print-quality-troubleshooting/layer-separation-and-splitting/

---

## 💡 Советы

- Начните с Simplify3D статей - они самые качественные
- Используйте административный интерфейс для визуальной проверки
- Проверяйте метаданные - они критически важны
- Тестируйте изображения - они улучшают диагностику


