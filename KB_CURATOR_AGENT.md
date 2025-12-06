# Агент-куратор KB (KB Curator Agent)

## 🎯 Назначение агента

**KB Curator Agent** — агент, который цензурирует информацию, извлеченную парсером, и готовит Q/A пары для KB.

**Задачи:**
1. ✅ **Цензурирование** — проверка извлеченной информации на релевантность и качество
2. ✅ **Фильтрация мусора** — удаление нерелевантной информации
3. ✅ **Подготовка Q/A** — формирование вопрос-ответ пар из статей
4. ✅ **Валидация метаданных** — проверка и улучшение метаданных

---

## 📋 Архитектура агента

```
┌─────────────────────────────────────────┐
│  Parser (извлекает информацию)          │
│  - HTML → текст                          │
│  - Извлечение метаданных                │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  KB Curator Agent (цензурирование)      │
│  ├── Content Validator                   │
│  │   - Проверка релевантности            │
│  │   - Проверка качества                 │
│  │   - Фильтрация мусора                 │
│  ├── Metadata Extractor                  │
│  │   - Извлечение структурированных      │
│  │     метаданных                         │
│  │   - Валидация метаданных              │
│  ├── QA Generator                        │
│  │   - Генерация Q/A пар из статьи       │
│  │   - Валидация Q/A                     │
│  └── KB Formatter                        │
│      - Форматирование для KB             │
│      - Подготовка к индексации           │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  KB (Qdrant)                            │
│  - Статьи                               │
│  - Q/A пары                             │
└─────────────────────────────────────────┘
```

---

## 🔍 Компоненты агента

### 1. Content Validator (Валидатор контента)

**Назначение:** Проверка релевантности и качества извлеченной информации

**Критерии проверки:**

```python
class ContentValidator:
    """Валидатор контента для KB"""
    
    def __init__(self, llm_client):
        self.llm = llm_client
        self.min_relevance_score = 0.7
        self.min_content_length = 200  # Минимум символов
    
    async def validate_content(self, article_content: dict) -> dict:
        """
        Валидация контента статьи
        
        Args:
            article_content: {
                "url": str,
                "title": str,
                "content": str,
                "section": str,
                "date": str
            }
        
        Returns:
            {
                "valid": bool,
                "relevance_score": float,
                "quality_score": float,
                "issues": List[str],
                "recommendations": List[str]
            }
        """
        
        # 1. Проверка длины контента
        if len(article_content["content"]) < self.min_content_length:
            return {
                "valid": False,
                "relevance_score": 0.0,
                "quality_score": 0.0,
                "issues": ["Контент слишком короткий"],
                "recommendations": []
            }
        
        # 2. Проверка релевантности через LLM
        relevance_check = await self._check_relevance(article_content)
        
        # 3. Проверка качества через LLM
        quality_check = await self._check_quality(article_content)
        
        # 4. Проверка наличия конкретных решений
        has_solutions = await self._check_solutions(article_content)
        
        # 5. Итоговая оценка
        is_valid = (
            relevance_check["relevance_score"] >= self.min_relevance_score and
            quality_check["quality_score"] >= 0.6 and
            has_solutions["has_solutions"]
        )
        
        return {
            "valid": is_valid,
            "relevance_score": relevance_check["relevance_score"],
            "quality_score": quality_check["quality_score"],
            "has_solutions": has_solutions["has_solutions"],
            "issues": relevance_check["issues"] + quality_check["issues"],
            "recommendations": relevance_check["recommendations"] + quality_check["recommendations"]
        }
    
    async def _check_relevance(self, article_content: dict) -> dict:
        """Проверка релевантности через LLM"""
        
        prompt = f"""
Проверь релевантность статьи для системы диагностики проблем 3D-печати.

СТАТЬЯ:
Заголовок: {article_content['title']}
Раздел: {article_content['section']}
Контент: {article_content['content'][:2000]}

КРИТЕРИИ РЕЛЕВАНТНОСТИ:
1. Содержит ли статья информацию о проблемах 3D-печати?
2. Есть ли конкретные решения или настройки?
3. Упоминаются ли модели принтеров, материалы, параметры?
4. Является ли информация полезной для диагностики?

Верни JSON:
{{
    "relevance_score": 0.0-1.0,
    "is_relevant": true/false,
    "issues": ["проблема1", "проблема2"],
    "recommendations": ["рекомендация1"]
}}
"""
        
        response = await self.llm.generate(prompt)
        return json.loads(response)
    
    async def _check_quality(self, article_content: dict) -> dict:
        """Проверка качества контента"""
        
        prompt = f"""
Оцени качество статьи для базы знаний.

СТАТЬЯ:
{article_content['content'][:2000]}

КРИТЕРИИ КАЧЕСТВА:
1. Структурированность (есть ли четкая структура?)
2. Конкретность (есть ли конкретные параметры, значения?)
3. Полнота (достаточно ли информации?)
4. Актуальность (не устарела ли информация?)

Верни JSON:
{{
    "quality_score": 0.0-1.0,
    "issues": ["проблема1"],
    "recommendations": ["рекомендация1"]
}}
"""
        
        response = await self.llm.generate(prompt)
        return json.loads(response)
    
    async def _check_solutions(self, article_content: dict) -> dict:
        """Проверка наличия конкретных решений"""
        
        # Простая проверка по ключевым словам
        content_lower = article_content["content"].lower()
        
        solution_keywords = [
            "увеличьте", "уменьшите", "установите", "настройте",
            "температура", "скорость", "retraction", "fan",
            "мм", "°c", "mm/s", "процент"
        ]
        
        has_keywords = sum(1 for kw in solution_keywords if kw in content_lower)
        has_solutions = has_keywords >= 3  # Минимум 3 ключевых слова
        
        return {
            "has_solutions": has_solutions,
            "keywords_found": has_keywords
        }
```

### 2. Metadata Extractor (Извлечение метаданных)

**Назначение:** Извлечение и валидация структурированных метаданных

```python
class MetadataExtractor:
    """Извлечение метаданных из статьи"""
    
    def __init__(self, llm_client):
        self.llm = llm_client
    
    async def extract_metadata(self, article_content: dict) -> dict:
        """
        Извлечение структурированных метаданных
        
        Returns:
            {
                "problem_type": str,
                "printer_models": List[str],
                "materials": List[str],
                "symptoms": List[str],
                "solutions": List[Dict],
                "print_stage": List[str],
                "confidence": float
            }
        """
        
        prompt = f"""
Извлеки структурированные метаданные из статьи о 3D-печати.

СТАТЬЯ:
Заголовок: {article_content['title']}
Контент: {article_content['content'][:3000]}

ИЗВЛЕКИ:
1. Тип проблемы (problem_type): stringing, warping, layer_separation, etc.
2. Модели принтеров (printer_models): Ender-3, Anycubic Kobra, etc.
3. Материалы (materials): PLA, PETG, ABS, etc.
4. Симптомы (symptoms): ["ниточки", "отслоение", ...]
5. Решения (solutions): [{{"parameter": "retraction_length", "value": 6, "unit": "mm"}}]
6. Этап печати (print_stage): first_layer, infill, etc.

ВАЖНО:
- Используй ТОЛЬКО информацию из статьи
- Не выдумывай, если информации нет - укажи null или []
- Будь точным в значениях параметров

Верни JSON:
{{
    "problem_type": "stringing" или null,
    "printer_models": ["Ender-3"] или [],
    "materials": ["PLA"] или [],
    "symptoms": ["ниточки"] или [],
    "solutions": [
        {{
            "parameter": "retraction_length",
            "value": 6,
            "unit": "mm",
            "description": "Увеличьте retraction до 6 мм"
        }}
    ] или [],
    "print_stage": ["first_layer"] или [],
    "confidence": 0.0-1.0
}}
"""
        
        response = await self.llm.generate(prompt)
        metadata = json.loads(response)
        
        # Валидация метаданных
        validated_metadata = self._validate_metadata(metadata)
        
        return validated_metadata
    
    def _validate_metadata(self, metadata: dict) -> dict:
        """Валидация извлеченных метаданных"""
        
        # Проверка типов
        if metadata.get("problem_type") and not isinstance(metadata["problem_type"], str):
            metadata["problem_type"] = None
        
        if metadata.get("printer_models") and not isinstance(metadata["printer_models"], list):
            metadata["printer_models"] = []
        
        if metadata.get("materials") and not isinstance(metadata["materials"], list):
            metadata["materials"] = []
        
        # Проверка solutions
        if metadata.get("solutions"):
            validated_solutions = []
            for sol in metadata["solutions"]:
                if isinstance(sol, dict) and "parameter" in sol and "value" in sol:
                    validated_solutions.append(sol)
            metadata["solutions"] = validated_solutions
        
        return metadata
```

### 3. QA Generator (Генератор Q/A)

**Назначение:** Формирование вопрос-ответ пар из статей

```python
class QAGenerator:
    """Генератор Q/A пар из статей"""
    
    def __init__(self, llm_client):
        self.llm = llm_client
    
    async def generate_qa_pairs(self, article: dict, metadata: dict) -> List[dict]:
        """
        Генерация Q/A пар из статьи
        
        Args:
            article: {
                "title": str,
                "content": str,
                "url": str
            }
            metadata: {
                "problem_type": str,
                "printer_models": List[str],
                "materials": List[str],
                "solutions": List[Dict]
            }
        
        Returns:
            List[{
                "question": str,
                "answer": str,
                "problem_type": str,
                "printer_models": List[str],
                "materials": List[str],
                "source_url": str,
                "confidence": float
            }]
        """
        
        prompt = f"""
Создай 3-5 вопрос-ответ пар для базы знаний на основе статьи.

СТАТЬЯ:
Заголовок: {article['title']}
Проблема: {metadata.get('problem_type', 'неизвестно')}
Принтеры: {', '.join(metadata.get('printer_models', []))}
Материалы: {', '.join(metadata.get('materials', []))}

СОДЕРЖАНИЕ:
{article['content'][:2000]}

РЕШЕНИЯ:
{json.dumps(metadata.get('solutions', []), ensure_ascii=False, indent=2)}

ТРЕБОВАНИЯ:
1. Вопросы должны быть реалистичными (как пользователи спрашивают)
2. Ответы должны содержать конкретные решения из статьи
3. Используй ТОЛЬКО информацию из статьи
4. Вопросы должны быть разной сложности

ФОРМАТ ВОПРОСОВ:
- Простые: "Как устранить stringing на Ender-3?"
- С контекстом: "У меня stringing при печати PLA на Ender-3, что делать?"
- С симптомами: "Печатаю PLA, везде ниточки между деталями, как исправить?"

Верни JSON:
{{
    "qa_pairs": [
        {{
            "question": "Как устранить stringing на Ender-3?",
            "answer": "Увеличьте retraction до 6 мм, скорость 45 мм/с...",
            "problem_type": "stringing",
            "printer_models": ["Ender-3"],
            "materials": ["PLA"],
            "confidence": 0.9
        }}
    ]
}}
"""
        
        response = await self.llm.generate(prompt)
        result = json.loads(response)
        
        # Добавление source_url к каждой паре
        qa_pairs = result.get("qa_pairs", [])
        for qa in qa_pairs:
            qa["source_url"] = article["url"]
        
        # Валидация Q/A пар
        validated_qa = self._validate_qa_pairs(qa_pairs)
        
        return validated_qa
    
    def _validate_qa_pairs(self, qa_pairs: List[dict]) -> List[dict]:
        """Валидация Q/A пар"""
        
        validated = []
        for qa in qa_pairs:
            # Проверка обязательных полей
            if not qa.get("question") or not qa.get("answer"):
                continue
            
            # Проверка минимальной длины
            if len(qa["question"]) < 10 or len(qa["answer"]) < 50:
                continue
            
            validated.append(qa)
        
        return validated
```

### 4. KB Formatter (Форматирование для KB)

**Назначение:** Подготовка данных для индексации в KB

```python
class KBFormatter:
    """Форматирование данных для KB"""
    
    def format_article(self, article: dict, metadata: dict, validation: dict) -> dict:
        """
        Форматирование статьи для KB
        
        Returns:
            {
                "article_id": str,
                "url": str,
                "title": str,
                "content": str,
                "section": str,
                "date": str,
                "relevance_score": float,
                "problem_type": str,
                "printer_models": List[str],
                "materials": List[str],
                "symptoms": List[str],
                "solutions": List[Dict],
                "print_stage": List[str],
                "related_problems": List[str],
                "last_updated": str,
                "usage_count": 0
            }
        """
        
        # Генерация article_id
        article_id = self._generate_article_id(article, metadata)
        
        # Форматирование
        formatted = {
            "article_id": article_id,
            "url": article["url"],
            "title": article["title"],
            "content": article["content"],
            "section": article.get("section", "unknown"),
            "date": article.get("date", datetime.now().isoformat()),
            "relevance_score": validation.get("relevance_score", 0.0),
            "problem_type": metadata.get("problem_type"),
            "printer_models": metadata.get("printer_models", []),
            "materials": metadata.get("materials", []),
            "symptoms": metadata.get("symptoms", []),
            "solutions": metadata.get("solutions", []),
            "print_stage": metadata.get("print_stage", []),
            "related_problems": metadata.get("related_problems", []),
            "last_updated": datetime.now().isoformat(),
            "usage_count": 0
        }
        
        return formatted
    
    def format_qa_pair(self, qa: dict) -> dict:
        """
        Форматирование Q/A пары для KB
        
        Returns:
            {
                "qa_id": str,
                "question": str,
                "answer": str,
                "problem_type": str,
                "printer_models": List[str],
                "materials": List[str],
                "source_url": str,
                "confidence": float,
                "created_at": str
            }
        """
        
        qa_id = f"qa_{hash(qa['question'])}_{datetime.now().timestamp()}"
        
        return {
            "qa_id": qa_id,
            "question": qa["question"],
            "answer": qa["answer"],
            "problem_type": qa.get("problem_type"),
            "printer_models": qa.get("printer_models", []),
            "materials": qa.get("materials", []),
            "source_url": qa.get("source_url"),
            "confidence": qa.get("confidence", 0.0),
            "created_at": datetime.now().isoformat()
        }
    
    def _generate_article_id(self, article: dict, metadata: dict) -> str:
        """Генерация уникального ID статьи"""
        
        # Используем problem_type + первые слова заголовка
        problem_type = metadata.get("problem_type", "unknown")
        title_words = article["title"].lower().split()[:3]
        title_slug = "_".join(title_words)
        
        return f"{problem_type}_{title_slug}"
```

---

## 🤖 Полный агент KB Curator

```python
class KBCuratorAgent:
    """Агент-куратор для цензурирования и подготовки данных для KB"""
    
    def __init__(self, llm_client, vector_db):
        self.content_validator = ContentValidator(llm_client)
        self.metadata_extractor = MetadataExtractor(llm_client)
        self.qa_generator = QAGenerator(llm_client)
        self.kb_formatter = KBFormatter()
        self.vector_db = vector_db
    
    async def process_article(self, parsed_article: dict) -> dict:
        """
        Обработка статьи: цензурирование и подготовка для KB
        
        Args:
            parsed_article: {
                "url": str,
                "title": str,
                "content": str,
                "section": str,
                "date": str
            }
        
        Returns:
            {
                "accepted": bool,
                "article": dict (если accepted=True),
                "qa_pairs": List[dict] (если accepted=True),
                "rejection_reason": str (если accepted=False),
                "validation": dict
            }
        """
        
        # 1. Валидация контента
        validation = await self.content_validator.validate_content(parsed_article)
        
        if not validation["valid"]:
            return {
                "accepted": False,
                "rejection_reason": "; ".join(validation["issues"]),
                "validation": validation
            }
        
        # 2. Извлечение метаданных
        metadata = await self.metadata_extractor.extract_metadata(parsed_article)
        
        # Проверка наличия problem_type (обязательное поле)
        if not metadata.get("problem_type"):
            return {
                "accepted": False,
                "rejection_reason": "Не удалось определить тип проблемы",
                "validation": validation,
                "metadata": metadata
            }
        
        # 3. Генерация Q/A пар
        qa_pairs = await self.qa_generator.generate_qa_pairs(parsed_article, metadata)
        
        if not qa_pairs:
            return {
                "accepted": False,
                "rejection_reason": "Не удалось сгенерировать Q/A пары",
                "validation": validation,
                "metadata": metadata
            }
        
        # 4. Форматирование для KB
        formatted_article = self.kb_formatter.format_article(
            parsed_article, metadata, validation
        )
        
        formatted_qa_pairs = [
            self.kb_formatter.format_qa_pair(qa) for qa in qa_pairs
        ]
        
        return {
            "accepted": True,
            "article": formatted_article,
            "qa_pairs": formatted_qa_pairs,
            "validation": validation,
            "metadata": metadata
        }
    
    async def index_to_kb(self, processed_result: dict) -> bool:
        """
        Индексация обработанной статьи в KB
        
        Returns:
            True если успешно, False если ошибка
        """
        
        if not processed_result["accepted"]:
            return False
        
        try:
            # Индексация статьи
            article = processed_result["article"]
            await self.vector_db.add_article(article)
            
            # Индексация Q/A пар
            for qa in processed_result["qa_pairs"]:
                await self.vector_db.add_qa_pair(qa)
            
            return True
        
        except Exception as e:
            logger.error(f"Ошибка индексации в KB: {e}")
            return False
```

---

## 🔄 Интеграция с парсером

**Полный pipeline:**

```python
async def parse_and_curate_article(url: str) -> dict:
    """Полный процесс: парсинг → цензурирование → индексация"""
    
    # 1. Парсинг
    parser = ArticleParser()
    parsed_article = await parser.parse(url)
    
    if not parsed_article:
        return {"error": "Не удалось распарсить статью"}
    
    # 2. Цензурирование через KB Curator Agent
    curator = KBCuratorAgent(llm_client, vector_db)
    processed_result = await curator.process_article(parsed_article)
    
    if not processed_result["accepted"]:
        return {
            "error": "Статья не прошла цензурирование",
            "reason": processed_result["rejection_reason"]
        }
    
    # 3. Индексация в KB
    success = await curator.index_to_kb(processed_result)
    
    if not success:
        return {"error": "Не удалось проиндексировать в KB"}
    
    return {
        "success": True,
        "article_id": processed_result["article"]["article_id"],
        "qa_count": len(processed_result["qa_pairs"])
    }
```

---

## 📊 Метрики работы агента

### Отслеживаемые метрики:

1. **Процент принятых статей**
   - Цель: > 70% статей проходят цензурирование
   - Если меньше → улучшить критерии отбора

2. **Качество метаданных**
   - Процент статей с полными метаданными
   - Цель: > 80%

3. **Качество Q/A пар**
   - Средняя уверенность (confidence)
   - Цель: > 0.8

4. **Время обработки**
   - Среднее время обработки статьи
   - Цель: < 30 секунд

---

## 🎯 Использование в MVP

### В реалистичном плане (2 недели):

**День 1-2: Ручной отбор статей**
- Использовать KB Curator Agent для валидации
- Ручной отбор → автоматическая валидация → индексация

**Процесс:**
1. Ручной отбор статьи из 3dtoday.ru
2. Парсинг (простой, без сложной логики)
3. **KB Curator Agent** проверяет и готовит для KB
4. Если принята → индексация
5. Если отклонена → анализ причин, улучшение

### Преимущества:

✅ **Автоматическая валидация** — не нужно вручную проверять каждую статью
✅ **Единообразные метаданные** — все статьи в одном формате
✅ **Готовые Q/A пары** — автоматическая генерация вопросов
✅ **Фильтрация мусора** — только качественные статьи попадают в KB

---

## 📝 Пример использования

```python
from backend.app.agents.kb_curator import KBCuratorAgent
from backend.app.services.llm_client import get_llm_client
from backend.app.services.vector_db import get_vector_db

# Инициализация
llm_client = get_llm_client()
vector_db = get_vector_db()
curator = KBCuratorAgent(llm_client, vector_db)

# Обработка статьи
parsed_article = {
    "url": "https://3dtoday.ru/...",
    "title": "Как устранить stringing на Ender-3",
    "content": "Полный текст статьи...",
    "section": "Техничка",
    "date": "2024-01-15"
}

result = await curator.process_article(parsed_article)

if result["accepted"]:
    print(f"✅ Статья принята: {result['article']['article_id']}")
    print(f"   Q/A пар: {len(result['qa_pairs'])}")
    print(f"   Релевантность: {result['validation']['relevance_score']:.2f}")
    
    # Индексация
    await curator.index_to_kb(result)
else:
    print(f"❌ Статья отклонена: {result['rejection_reason']}")
```

---

## 🔧 Конфигурация

**Настройки в config.env:**

```env
# KB Curator Agent Configuration
KB_CURATOR_MIN_RELEVANCE=0.7
KB_CURATOR_MIN_QUALITY=0.6
KB_CURATOR_MIN_CONTENT_LENGTH=200
KB_CURATOR_QA_COUNT=3-5
KB_CURATOR_USE_LLM_VALIDATION=true
```

---

## 📚 Структура файлов

```
backend/app/agents/
├── __init__.py
├── kb_curator.py          # Основной класс KBCuratorAgent
├── content_validator.py   # ContentValidator
├── metadata_extractor.py # MetadataExtractor
├── qa_generator.py        # QAGenerator
└── kb_formatter.py        # KBFormatter
```

---

## ✅ Чек-лист реализации

### День 1-2 (в рамках MVP):
- [ ] Реализовать ContentValidator
- [ ] Реализовать MetadataExtractor
- [ ] Реализовать QAGenerator
- [ ] Реализовать KBFormatter
- [ ] Интегрировать в KBCuratorAgent
- [ ] Тестирование на 2-3 статьях

### Интеграция:
- [ ] Интеграция с парсером
- [ ] Интеграция с векторной БД
- [ ] Логирование работы агента
- [ ] Метрики работы

---

## 🎯 Критерии успеха

✅ **Валидация работает** — отклоняет нерелевантные статьи
✅ **Метаданные извлекаются** — > 80% статей с полными метаданными
✅ **Q/A пары генерируются** — 3-5 пар на статью
✅ **Время обработки** — < 30 секунд на статью

---

## 💡 Будущие улучшения

### Краткосрочные (1-2 месяца):
- Улучшение промптов для LLM
- Более точное извлечение метаданных
- Валидация Q/A пар на основе реальных запросов

### Долгосрочные (3-6 месяцев):
- Обучение на реальных данных
- Автоматическая оптимизация критериев
- Интеграция с обратной связью пользователей



