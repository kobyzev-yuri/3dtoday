# Стратегия парсинга, тестирования и архитектуры агентов

## 📋 Содержание

1. [Интеллектуальный парсинг сайта 3dtoday.ru](#1-интеллектуальный-парсинг-сайта-3dtodayru)
2. [Тестирование KB на релевантность](#2-тестирование-kb-на-релевантность)
3. [Архитектура взаимодействия агентов](#3-архитектура-взаимодействия-агентов)

---

## 1. Интеллектуальный парсинг сайта 3dtoday.ru

### 1.1 Цель парсинга

**Задача:** Извлечь только релевантную информацию, соответствующую задачам проекта, минимизировав загрузку "мусора" в KB.

**Критерии релевантности:**
- ✅ Статьи по диагностике и решению проблем 3D-печати
- ✅ Информация о настройке принтеров и материалов
- ✅ Реальные кейсы с проблемами и решениями
- ❌ Акции, объявления, обсуждения без технической ценности
- ❌ Устаревшая информация (старые модели принтеров)

### 1.2 Многоуровневая фильтрация

#### Уровень 1: Структурная фильтрация (до парсинга)

**Фильтрация по разделам сайта:**

```python
RELEVANT_SECTIONS = {
    "Техничка": {
        "priority": "high",
        "subsections": ["Настройка", "Устранение неполадок", "Калибровка"]
    },
    "3D-печать": {
        "priority": "high",
        "subsections": ["Методики", "Технологии", "Материалы"]
    },
    "3d-Оборудование → 3D-принтеры": {
        "priority": "medium",
        "subsections": ["Характеристики", "Настройка", "Проблемы"]
    },
    "Расходные материалы": {
        "priority": "high",
        "subsections": ["PLA", "PETG", "ABS", "Настройки"]
    },
    "Применение": {
        "priority": "medium",
        "subsections": ["Кейсы", "Проблемы и решения"]
    },
    "Личные дневники": {
        "priority": "low",
        "filter": "only_technical_content"  # Только технические посты
    }
}

EXCLUDED_SECTIONS = [
    "Акции",
    "Песочница",
    "Частные объявления",
    "Новости",
    "Форум (общие обсуждения)"
]
```

**Реализация:**

```python
class SectionFilter:
    def __init__(self):
        self.relevant_sections = RELEVANT_SECTIONS
        self.excluded_sections = EXCLUDED_SECTIONS
    
    def is_relevant(self, url: str, section: str) -> bool:
        """Проверка релевантности раздела"""
        if section in self.excluded_sections:
            return False
        
        if section in self.relevant_sections:
            return True
        
        return False
    
    def get_priority(self, section: str) -> str:
        """Получить приоритет раздела"""
        return self.relevant_sections.get(section, {}).get("priority", "low")
```

#### Уровень 2: Контентная фильтрация (после парсинга)

**Использование LLM для анализа релевантности:**

```python
class ContentRelevanceFilter:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    async def analyze_relevance(self, article_content: str, metadata: dict) -> dict:
        """Анализ релевантности статьи с помощью LLM"""
        
        prompt = f"""
Проанализируй статью и определи её релевантность для системы диагностики проблем 3D-печати.

СТАТЬЯ:
{article_content[:2000]}

МЕТАДАННЫЕ:
- Раздел: {metadata.get('section')}
- Заголовок: {metadata.get('title')}
- Дата: {metadata.get('date')}

КРИТЕРИИ РЕЛЕВАНТНОСТИ:
1. Содержит ли статья информацию о проблемах 3D-печати?
2. Есть ли конкретные решения или настройки?
3. Упоминаются ли модели принтеров, материалы, параметры?
4. Является ли информация актуальной и полезной?

Верни JSON:
{{
    "relevant": true/false,
    "relevance_score": 0.0-1.0,
    "problem_types": ["stringing", "warping", ...],
    "printer_models": ["Ender-3", ...],
    "materials": ["PLA", "PETG", ...],
    "has_solutions": true/false,
    "has_parameters": true/false,
    "reason": "почему релевантна/не релевантна"
}}
"""
        
        response = await self.llm.generate(prompt)
        return json.loads(response)
    
    def should_include(self, analysis: dict, min_score: float = 0.7) -> bool:
        """Решение о включении статьи в KB"""
        if not analysis.get("relevant", False):
            return False
        
        if analysis.get("relevance_score", 0.0) < min_score:
            return False
        
        # Дополнительные проверки
        if not analysis.get("has_solutions", False):
            return False  # Нужны конкретные решения
        
        return True
```

#### Уровень 3: Извлечение структурированных данных

**Парсинг метаданных из статьи:**

```python
class ArticleMetadataExtractor:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    async def extract_metadata(self, article_content: str, url: str) -> dict:
        """Извлечение структурированных метаданных из статьи"""
        
        prompt = f"""
Извлеки структурированные метаданные из статьи о 3D-печати.

СТАТЬЯ:
{article_content[:3000]}

Извлеки:
1. Типы проблем (problem_type): stringing, warping, layer_separation, etc.
2. Модели принтеров (printer_models): Ender-3, Anycubic Kobra, etc.
3. Материалы (materials): PLA, PETG, ABS, etc.
4. Симптомы (symptoms): ["ниточки", "отслоение", ...]
5. Решения (solutions): [{{"parameter": "retraction_length", "value": 6, ...}}]
6. Этап печати (print_stage): first_layer, infill, etc.

Верни JSON:
{{
    "problem_type": "stringing",
    "printer_models": ["Ender-3"],
    "materials": ["PLA"],
    "symptoms": ["ниточки", "сопли"],
    "solutions": [
        {{
            "parameter": "retraction_length",
            "value": 6,
            "unit": "mm",
            "description": "Увеличьте retraction до 6 мм"
        }}
    ],
    "print_stage": ["first_layer"],
    "related_problems": ["warping", "overheating"]
}}
"""
        
        response = await self.llm.generate(prompt)
        return json.loads(response)
```

### 1.3 Парсер с интеллектуальной фильтрацией

**Полный pipeline парсинга:**

```python
class IntelligentScraper:
    def __init__(self, llm_client, vector_db):
        self.section_filter = SectionFilter()
        self.relevance_filter = ContentRelevanceFilter(llm_client)
        self.metadata_extractor = ArticleMetadataExtractor(llm_client)
        self.vector_db = vector_db
    
    async def scrape_article(self, url: str) -> Optional[dict]:
        """Парсинг статьи с многоуровневой фильтрацией"""
        
        # 1. Получение HTML
        html = await self.fetch_html(url)
        
        # 2. Структурная фильтрация
        section = self.extract_section(html)
        if not self.section_filter.is_relevant(url, section):
            logger.info(f"⏭️ Пропущена статья: {url} (раздел: {section})")
            return None
        
        # 3. Извлечение контента
        article_content = self.extract_content(html)
        metadata = {
            "url": url,
            "section": section,
            "title": self.extract_title(html),
            "date": self.extract_date(html)
        }
        
        # 4. Анализ релевантности
        relevance_analysis = await self.relevance_filter.analyze_relevance(
            article_content, metadata
        )
        
        if not self.relevance_filter.should_include(relevance_analysis):
            logger.info(f"⏭️ Пропущена статья: {url} (score: {relevance_analysis['relevance_score']})")
            return None
        
        # 5. Извлечение структурированных метаданных
        structured_metadata = await self.metadata_extractor.extract_metadata(
            article_content, url
        )
        
        # 6. Формирование финального объекта
        article = {
            "url": url,
            "title": metadata["title"],
            "content": article_content,
            "section": section,
            "date": metadata["date"],
            "relevance_score": relevance_analysis["relevance_score"],
            "problem_type": structured_metadata.get("problem_type"),
            "printer_models": structured_metadata.get("printer_models", []),
            "materials": structured_metadata.get("materials", []),
            "symptoms": structured_metadata.get("symptoms", []),
            "solutions": structured_metadata.get("solutions", []),
            "print_stage": structured_metadata.get("print_stage", []),
            "related_problems": structured_metadata.get("related_problems", [])
        }
        
        logger.info(f"✅ Статья добавлена: {url} (score: {relevance_analysis['relevance_score']:.2f})")
        return article
    
    async def scrape_section(self, section_url: str, max_articles: int = 100):
        """Парсинг раздела с ограничением количества"""
        articles = []
        page = 1
        
        while len(articles) < max_articles:
            page_url = f"{section_url}?page={page}"
            article_urls = await self.extract_article_urls(page_url)
            
            if not article_urls:
                break
            
            for url in article_urls:
                if len(articles) >= max_articles:
                    break
                
                article = await self.scrape_article(url)
                if article:
                    articles.append(article)
                    # Небольшая задержка между запросами
                    await asyncio.sleep(1)
            
            page += 1
        
        return articles
```

### 1.4 Приоритизация парсинга

**Стратегия:**
1. **Высокий приоритет** — парсить первыми
   - Техничка → Настройка, Устранение неполадок
   - Расходные материалы → PLA, PETG, ABS
   
2. **Средний приоритет** — парсить после высокого
   - 3D-печать → Методики
   - Применение → Кейсы
   
3. **Низкий приоритет** — парсить в последнюю очередь
   - Личные дневники (только технические посты)

**Реализация:**

```python
async def scrape_with_priority(self):
    """Парсинг с учетом приоритетов"""
    
    # Высокий приоритет
    high_priority_sections = [
        "Техничка/Настройка",
        "Техничка/Устранение неполадок",
        "Расходные материалы/PLA",
        "Расходные материалы/PETG"
    ]
    
    for section in high_priority_sections:
        articles = await self.scrape_section(section, max_articles=50)
        await self.index_articles(articles)
    
    # Средний приоритет
    medium_priority_sections = [
        "3D-печать/Методики",
        "Применение/Кейсы"
    ]
    
    for section in medium_priority_sections:
        articles = await self.scrape_section(section, max_articles=30)
        await self.index_articles(articles)
```

---

## 2. Тестирование KB на релевантность

### 2.1 Методология тестирования (из ai_report и steccom-rag-lk)

#### Метрики качества

**1. Top-k Hit Rate (Точность ретривера)**
- **Определение:** Доля запросов, где релевантная статья попала в top-k результатов
- **Целевые значения:**
  - Top-1: > 0.6 (60%)
  - Top-3: > 0.8 (80%)
  - Top-5: > 0.9 (90%)

**2. Relevance Score (Оценка релевантности)**
- **Определение:** Процент найденных ключевых слов в ответе
- **Метод:** Сравнение ожидаемых ключевых слов с найденными
- **Целевое значение:** > 0.7 (70%)

**3. MRR (Mean Reciprocal Rank)**
- **Определение:** Усредненная обратная позиция первого релевантного результата
- **Формула:** `MRR = (1/n) * Σ(1/rank_i)`
- **Целевое значение:** > 0.7

**4. Diagnostic Accuracy (Точность диагностики)**
- **Определение:** Доля правильных диагнозов проблем
- **Метод:** Сравнение диагноза системы с эталонным
- **Целевое значение:** > 0.8 (80%)

### 2.2 Генерация тестовых вопросов

**Подход из steccom-rag-lk:**

```python
class RelevanceTestGenerator:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    async def generate_test_questions(self, article: dict) -> List[dict]:
        """Генерация тестовых вопросов на основе статьи"""
        
        prompt = f"""
Создай 5-7 тестовых вопросов для проверки релевантности статьи в базе знаний.

СТАТЬЯ:
Заголовок: {article['title']}
Проблема: {article['problem_type']}
Принтеры: {', '.join(article['printer_models'])}
Материалы: {', '.join(article['materials'])}

СОДЕРЖАНИЕ:
{article['content'][:2000]}

ТРЕБОВАНИЯ:
1. Вопросы должны проверять релевантность статьи
2. Каждый вопрос должен иметь ожидаемые ключевые слова
3. Вопросы должны быть реалистичными (как пользователи спрашивают)
4. Разная сложность: простые и сложные вопросы

Верни JSON:
{{
    "questions": [
        {{
            "question": "Как устранить stringing на Ender-3?",
            "expected_keywords": ["retraction", "температура", "6 мм"],
            "category": "stringing",
            "difficulty": "medium",
            "expected_answer": "Увеличьте retraction до 6 мм..."
        }}
    ]
}}
"""
        
        response = await self.llm.generate(prompt)
        return json.loads(response)["questions"]
```

### 2.3 Тестирование KB

**Полный pipeline тестирования:**

```python
class KBRelevanceTester:
    def __init__(self, rag_service, llm_client):
        self.rag = rag_service
        self.llm = llm_client
        self.test_questions = []
    
    async def test_kb_relevance(self, test_questions: List[dict]) -> dict:
        """Тестирование KB на релевантность"""
        
        results = {
            "total_questions": len(test_questions),
            "top_1_hits": 0,
            "top_3_hits": 0,
            "top_5_hits": 0,
            "avg_relevance_score": 0.0,
            "mrr": 0.0,
            "details": []
        }
        
        for question_data in test_questions:
            question = question_data["question"]
            expected_keywords = question_data["expected_keywords"]
            
            # Поиск в KB
            search_results = await self.rag.search(
                query=question,
                limit=5,
                filters={
                    "problem_type": question_data.get("category"),
                    "printer_models": question_data.get("printer_models", []),
                    "materials": question_data.get("materials", [])
                }
            )
            
            # Генерация ответа
            answer = await self.rag.generate_answer(
                question=question,
                context=search_results
            )
            
            # Оценка релевантности
            relevance_score = self._calculate_relevance_score(
                answer, expected_keywords
            )
            
            # Проверка попадания в top-k
            is_relevant = self._check_relevance(
                search_results, question_data.get("expected_article_id")
            )
            
            rank = self._find_relevant_rank(
                search_results, question_data.get("expected_article_id")
            )
            
            # Обновление метрик
            if rank == 1:
                results["top_1_hits"] += 1
            if rank <= 3:
                results["top_3_hits"] += 1
            if rank <= 5:
                results["top_5_hits"] += 1
            
            if rank > 0:
                results["mrr"] += 1.0 / rank
            
            results["avg_relevance_score"] += relevance_score
            
            results["details"].append({
                "question": question,
                "relevance_score": relevance_score,
                "rank": rank,
                "is_relevant": is_relevant
            })
        
        # Нормализация метрик
        results["top_1_hits"] /= results["total_questions"]
        results["top_3_hits"] /= results["total_questions"]
        results["top_5_hits"] /= results["total_questions"]
        results["mrr"] /= results["total_questions"]
        results["avg_relevance_score"] /= results["total_questions"]
        
        return results
    
    def _calculate_relevance_score(self, answer: str, expected_keywords: List[str]) -> float:
        """Расчет оценки релевантности по ключевым словам"""
        answer_lower = answer.lower()
        found_keywords = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
        return found_keywords / len(expected_keywords) if expected_keywords else 0.0
    
    def _check_relevance(self, results: List[dict], expected_id: str) -> bool:
        """Проверка наличия релевантной статьи в результатах"""
        if not expected_id:
            return False
        return any(r.get("id") == expected_id for r in results)
    
    def _find_relevant_rank(self, results: List[dict], expected_id: str) -> int:
        """Поиск позиции релевантной статьи"""
        if not expected_id:
            return -1
        for i, result in enumerate(results, 1):
            if result.get("id") == expected_id:
                return i
        return -1
```

### 2.4 Итеративное улучшение KB

**Процесс на основе метрик:**

```python
class KBIterativeImprover:
    def __init__(self, kb_tester, scraper):
        self.tester = kb_tester
        self.scraper = scraper
    
    async def improve_kb(self, test_results: dict):
        """Улучшение KB на основе результатов тестирования"""
        
        recommendations = []
        
        # Анализ слабых мест
        if test_results["top_1_hits"] < 0.6:
            recommendations.append({
                "issue": "Низкая точность Top-1",
                "action": "Добавить больше статей по проблемным категориям",
                "priority": "high"
            })
        
        if test_results["avg_relevance_score"] < 0.7:
            recommendations.append({
                "issue": "Низкая релевантность ответов",
                "action": "Улучшить метаданные статей, добавить больше ключевых слов",
                "priority": "high"
            })
        
        # Анализ детальных результатов
        weak_questions = [
            d for d in test_results["details"]
            if d["relevance_score"] < 0.5 or d["rank"] > 3
        ]
        
        if weak_questions:
            # Определение проблемных категорий
            problem_categories = {}
            for q in weak_questions:
                category = q.get("category", "unknown")
                problem_categories[category] = problem_categories.get(category, 0) + 1
            
            # Рекомендации по парсингу
            for category, count in problem_categories.items():
                recommendations.append({
                    "issue": f"Недостаточно статей по категории: {category}",
                    "action": f"Парсить больше статей из раздела '{category}'",
                    "priority": "medium",
                    "count": count
                })
        
        return recommendations
```

---

## 3. Архитектура взаимодействия агентов

### 3.1 Принципы согласованности

**1. Единый контекст сессии**
- Все агенты работают с одним объектом `SessionContext`
- Контекст передается между агентами
- История диалога сохраняется в контексте

**2. Четкие роли агентов**
- Каждый агент имеет четко определенную роль
- Нет пересечения функций между агентами
- Агенты не конфликтуют друг с другом

**3. Согласованные метаданные**
- Единый формат метаданных для всех агентов
- Консистентная структура данных
- Валидация данных между агентами

### 3.2 Архитектура агентов

```
┌─────────────────────────────────────────────┐
│  Orchestrator Agent (главный координатор)   │
│  - Управляет потоком диалога                │
│  - Решает, какой агент вызвать              │
│  - Поддерживает SessionContext              │
│  - Обрабатывает ошибки и fallback           │
└─────────────────────────────────────────────┘
           │
           ├───► Vision Agent
           │     Input: image bytes
           │     Output: {problem_type, symptoms, description}
           │     Context: SessionContext (добавляет vision_result)
           │
           ├───► Diagnostic Agent
           │     Input: user_input, context
           │     Output: {questions, diagnosis, confidence}
           │     Context: SessionContext (обновляет diagnostic_state)
           │
           └───► Retrieval Agent
                 Input: query, filters
                 Output: {articles, relevance_scores}
                 Context: SessionContext (использует filters из context)
```

### 3.3 SessionContext (единый контекст)

```python
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from datetime import datetime

@dataclass
class SessionContext:
    """Единый контекст сессии для всех агентов"""
    
    # Идентификация
    session_id: str
    user_id: Optional[str] = None
    
    # История диалога
    messages: List[Dict[str, Any]] = None
    
    # Состояние диагностики
    diagnostic_state: str = "initial"  # initial, collecting_info, diagnosing, solved
    current_problem_type: Optional[str] = None
    collected_info: Dict[str, Any] = None
    
    # Результаты Vision Agent
    vision_result: Optional[Dict[str, Any]] = None
    
    # Результаты Retrieval Agent
    retrieved_articles: List[Dict[str, Any]] = None
    
    # Контекст пользователя
    printer_model: Optional[str] = None
    material: Optional[str] = None
    print_stage: Optional[str] = None
    
    # Метаданные
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.messages is None:
            self.messages = []
        if self.collected_info is None:
            self.collected_info = {}
        if self.retrieved_articles is None:
            self.retrieved_articles = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def add_message(self, role: str, content: str, metadata: Dict = None):
        """Добавить сообщение в историю"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        })
        self.updated_at = datetime.now()
    
    def get_filters(self) -> Dict[str, Any]:
        """Получить фильтры для RAG на основе контекста"""
        filters = {}
        
        if self.current_problem_type:
            filters["problem_type"] = self.current_problem_type
        
        if self.printer_model:
            filters["printer_models"] = [self.printer_model]
        
        if self.material:
            filters["materials"] = [self.material]
        
        if self.print_stage:
            filters["print_stage"] = [self.print_stage]
        
        return filters
```

### 3.4 Взаимодействие агентов

**Пример потока:**

```python
class OrchestratorAgent:
    def __init__(self, vision_agent, diagnostic_agent, retrieval_agent):
        self.vision = vision_agent
        self.diagnostic = diagnostic_agent
        self.retrieval = retrieval_agent
    
    async def process_request(
        self, 
        user_input: str, 
        image: Optional[bytes],
        context: SessionContext
    ) -> Dict[str, Any]:
        """Обработка запроса пользователя"""
        
        # 1. Обработка изображения (если есть)
        if image:
            vision_result = await self.vision.analyze_image(image, context)
            context.vision_result = vision_result
            context.current_problem_type = vision_result.get("problem_type")
            
            # Обновляем user_input с результатами анализа
            user_input += f" {vision_result.get('description', '')}"
        
        # 2. Диагностика
        diagnostic_result = await self.diagnostic.diagnose(user_input, context)
        context.diagnostic_state = diagnostic_result["state"]
        
        # 3. Поиск в KB (если нужно)
        if diagnostic_result["needs_kb_search"]:
            filters = context.get_filters()
            search_results = await self.retrieval.search(
                query=user_input,
                filters=filters,
                limit=5
            )
            context.retrieved_articles = search_results
        
        # 4. Формирование ответа
        response = await self._formulate_response(context, diagnostic_result)
        
        # 5. Обновление контекста
        context.add_message("user", user_input)
        context.add_message("assistant", response["text"])
        
        return response
    
    async def _formulate_response(
        self, 
        context: SessionContext, 
        diagnostic_result: Dict
    ) -> Dict[str, Any]:
        """Формирование финального ответа"""
        
        # Если есть вопросы для уточнения
        if diagnostic_result.get("questions"):
            return {
                "type": "clarification",
                "text": diagnostic_result["questions"][0],
                "questions": diagnostic_result["questions"]
            }
        
        # Если есть решение
        if diagnostic_result.get("solution"):
            articles = context.retrieved_articles or []
            return {
                "type": "solution",
                "text": diagnostic_result["solution"],
                "articles": articles,
                "confidence": diagnostic_result.get("confidence", 0.0)
            }
        
        return {
            "type": "unknown",
            "text": "Не удалось определить проблему. Можете описать подробнее?"
        }
```

### 3.5 Согласованность метаданных

**Единый формат метаданных:**

```python
ARTICLE_METADATA_SCHEMA = {
    "problem_type": str,  # "stringing", "warping", etc.
    "printer_models": List[str],  # ["Ender-3", "Ender-3 V2"]
    "materials": List[str],  # ["PLA", "PETG"]
    "symptoms": List[str],  # ["ниточки", "сопли"]
    "print_stage": List[str],  # ["first_layer", "infill"]
    "solutions": List[Dict],  # [{"parameter": "...", "value": ...}]
    "related_problems": List[str]  # ["warping", "overheating"]
}

def validate_metadata(metadata: dict) -> bool:
    """Валидация метаданных"""
    for key, expected_type in ARTICLE_METADATA_SCHEMA.items():
        if key not in metadata:
            continue  # Опциональные поля
        
        value = metadata[key]
        if expected_type == List[str]:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                return False
        elif expected_type == str:
            if not isinstance(value, str):
                return False
    
    return True
```

### 3.6 Обработка конфликтов

**Стратегия разрешения конфликтов:**

```python
class ConflictResolver:
    def resolve_vision_diagnostic_conflict(
        self, 
        vision_result: Dict, 
        diagnostic_result: Dict
    ) -> Dict:
        """Разрешение конфликта между Vision и Diagnostic агентами"""
        
        vision_problem = vision_result.get("problem_type")
        diagnostic_problem = diagnostic_result.get("problem_type")
        
        if vision_problem == diagnostic_problem:
            return {
                "resolved": True,
                "problem_type": vision_problem,
                "confidence": max(
                    vision_result.get("confidence", 0.0),
                    diagnostic_result.get("confidence", 0.0)
                )
            }
        
        # Конфликт: разные проблемы
        # Приоритет: Vision (если уверенность высокая)
        if vision_result.get("confidence", 0.0) > 0.8:
            return {
                "resolved": True,
                "problem_type": vision_problem,
                "confidence": vision_result.get("confidence", 0.0),
                "note": "Приоритет Vision Agent (высокая уверенность)"
            }
        
        # Иначе запрашиваем уточнение у пользователя
        return {
            "resolved": False,
            "conflict": True,
            "vision_suggestion": vision_problem,
            "diagnostic_suggestion": diagnostic_problem,
            "question": f"По фото похоже на '{vision_problem}', но по описанию - '{diagnostic_problem}'. Что именно происходит?"
        }
```

---

## 4. План реализации

### Этап 1: Парсер (1-2 недели)

1. **Структурная фильтрация** (2-3 дня)
   - Реализация `SectionFilter`
   - Парсинг структуры сайта
   - Фильтрация по разделам

2. **Контентная фильтрация** (3-4 дня)
   - Реализация `ContentRelevanceFilter`
   - Интеграция с LLM для анализа
   - Тестирование на выборке статей

3. **Извлечение метаданных** (2-3 дня)
   - Реализация `ArticleMetadataExtractor`
   - Парсинг структурированных данных
   - Валидация метаданных

### Этап 2: Тестирование KB (1 неделя)

1. **Генерация тестовых вопросов** (2-3 дня)
   - Реализация `RelevanceTestGenerator`
   - Создание тестового набора
   - Валидация вопросов

2. **Тестирование** (2-3 дня)
   - Реализация `KBRelevanceTester`
   - Запуск тестов
   - Анализ результатов

3. **Итеративное улучшение** (1-2 дня)
   - Реализация `KBIterativeImprover`
   - Генерация рекомендаций
   - Обновление KB

### Этап 3: Архитектура агентов (1 неделя)

1. **SessionContext** (1-2 дня)
   - Реализация класса
   - Интеграция с агентами
   - Тестирование

2. **Orchestrator Agent** (2-3 дня)
   - Реализация координации
   - Обработка ошибок
   - Fallback логика

3. **Согласованность** (1-2 дня)
   - Валидация метаданных
   - Разрешение конфликтов
   - Тестирование взаимодействия

---

## 5. Метрики успеха

### Парсинг
- ✅ **Точность фильтрации:** > 90% релевантных статей
- ✅ **Покрытие метаданных:** > 80% статей с полными метаданными
- ✅ **Скорость парсинга:** > 10 статей/минуту

### Тестирование KB
- ✅ **Top-1 Hit Rate:** > 0.6
- ✅ **Top-3 Hit Rate:** > 0.8
- ✅ **Relevance Score:** > 0.7
- ✅ **MRR:** > 0.7

### Агенты
- ✅ **Согласованность:** 100% (нет конфликтов метаданных)
- ✅ **Время ответа:** < 5 секунд
- ✅ **Точность диагностики:** > 0.8

