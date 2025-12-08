"""
Агент-библиотекарь для анализа статей
Делает краткое изложение проблемы и решения
Поддерживает разные типы контента: проблемы, документация, сравнения, технические детали
Принимает решение о публикации в KB с проверкой на дублирование и релевантность
"""

import os
import logging
import json
import httpx
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / "config.env")

# Настройка логирования с записью в файл
try:
    from app.utils.logger_config import get_librarian_logger
    logger = get_librarian_logger()
except ImportError:
    # Fallback если logger_config недоступен
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


class KBLibrarianAgent:
    """
    Агент-библиотекарь для анализа документов
    Анализирует текст и изображения, делает краткое изложение
    Принимает решение о публикации в KB
    """
    
    def __init__(self, llm_provider: Optional[str] = None, model: Optional[str] = None, timeout: Optional[int] = None):
        """
        Инициализация агента
        
        Args:
            llm_provider: Провайдер LLM (openai, ollama, gemini). Если не указан, используется из config.env
            model: Модель для использования. Если не указана, используется из config.env
            timeout: Таймаут для LLM запросов
        """
        self.llm_provider = llm_provider
        self.model = model
        self.timeout = timeout
        self.llm_client = None
        self.vector_db = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Инициализация зависимых сервисов"""
        try:
            # Импорт с правильными путями
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            
            try:
                from backend.app.services.llm_client import get_llm_client, reset_llm_client
                from backend.app.services.vector_db import get_vector_db
            except ImportError:
                from app.services.llm_client import get_llm_client, reset_llm_client
                from app.services.vector_db import get_vector_db
            
            # Если указан провайдер или модель, временно меняем переменные окружения
            original_provider = None
            original_model = None
            
            if self.llm_provider:
                original_provider = os.getenv("LLM_PROVIDER")
                os.environ["LLM_PROVIDER"] = self.llm_provider
            
            if self.model:
                if self.llm_provider == "openai":
                    original_model = os.getenv("OPENAI_MODEL")
                    os.environ["OPENAI_MODEL"] = self.model
                elif self.llm_provider == "ollama":
                    original_model = os.getenv("OLLAMA_MODEL")
                    os.environ["OLLAMA_MODEL"] = self.model
                elif self.llm_provider == "gemini":
                    original_model = os.getenv("GEMINI_MODEL")
                    os.environ["GEMINI_MODEL"] = self.model
            
            if self.timeout:
                if self.llm_provider == "openai":
                    os.environ["OPENAI_TIMEOUT"] = str(self.timeout)
                elif self.llm_provider == "ollama":
                    os.environ["OLLAMA_TIMEOUT"] = str(self.timeout)
                elif self.llm_provider == "gemini":
                    os.environ["GEMINI_TIMEOUT"] = str(self.timeout)
            
            # Сбрасываем синглтон, чтобы переинициализировать с новыми настройками
            if self.llm_provider:
                reset_llm_client()
            
            # Сохраняем оригинальные настройки для восстановления позже
            self._original_provider = original_provider
            self._original_model = original_model
            self._original_provider_name = self.llm_provider
            
            # Создаем клиент с правильным провайдером напрямую
            # Это гарантирует, что будет использован нужный провайдер, а не Ollama
            self.llm_client = get_llm_client(provider=self.llm_provider)
            self.vector_db = get_vector_db()
            
            # ВАЖНО: НЕ восстанавливаем настройки сразу!
            # Они будут восстановлены только после завершения работы агента
            # Это гарантирует, что клиент будет использовать правильный провайдер
            
            logger.info(f"✅ KBLibrarianAgent инициализирован (provider={self.llm_provider or 'default'}, model={self.model or 'default'})")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации KBLibrarianAgent: {e}")
            raise
    
    async def review_and_decide(
        self,
        title: str,
        content: str,
        images: Optional[List[Dict[str, Any]]] = None,
        url: Optional[str] = None,
        content_type: Optional[str] = None,
        is_questions_list: bool = False
    ) -> Dict[str, Any]:
        """
        Полный цикл: анализ документа, проверка на дублирование, принятие решения о публикации
        
        Args:
            is_questions_list: True если это страница со списком вопросов (не добавлять в KB)
        
        Returns:
            {
                "decision": "approve|reject|needs_review",
                "reason": "причина решения",
                "relevance_score": 0.0-1.0,
                "duplicate_check": {...},
                "abstract": "краткое изложение",
                "summary": {...},
                "recommendations": [...]
            }
        """
        try:
            # Если это список вопросов - сразу отклоняем
            if is_questions_list:
                return {
                    "decision": "reject",
                    "reason": "Это страница со списком вопросов, а не отдельная статья. Используйте URL конкретного вопроса для добавления в KB.",
                    "relevance_score": 0.0,
                    "quality_score": 0.0,
                    "duplicate_check": {"is_duplicate": False},
                    "abstract": "",
                    "summary": {},
                    "filtered_content": "",
                    "recommendations": ["Используйте URL конкретного вопроса из списка"]
                }
            # Шаг 1: Анализ документа
            summary = await self.analyze_article(
                title=title,
                content=content,
                images=images,
                url=url,
                content_type=content_type
            )
            
            # Шаг 2: Проверка релевантности и качества
            relevance_check = await self._check_relevance(title, content, summary)
            
            # Шаг 3: Проверка на дублирование
            duplicate_check = await self._check_duplicates(title, content, summary)
            
            # Шаг 4: Создание качественного abstract
            abstract = await self._create_abstract(title, content, summary)
            
            # Шаг 5: Фильтрация несущественной информации
            filtered_content = await self._filter_irrelevant_content(content, summary)
            
            # Шаг 6: Принятие решения
            decision = await self._make_decision(
                relevance_check=relevance_check,
                duplicate_check=duplicate_check,
                summary=summary,
                abstract=abstract
            )
            
            return {
                "decision": decision["decision"],
                "reason": decision["reason"],
                "relevance_score": relevance_check.get("score", 0.0),
                "quality_score": relevance_check.get("quality_score", 0.0),
                "duplicate_check": duplicate_check,
                "abstract": abstract,
                "summary": summary,
                "filtered_content": filtered_content,
                "recommendations": decision.get("recommendations", []),
                "key_points": summary.get("key_points", [])
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа и принятия решения: {e}", exc_info=True)
            return {
                "decision": "needs_review",
                "reason": f"Ошибка анализа: {str(e)}",
                "relevance_score": 0.0,
                "duplicate_check": {"is_duplicate": False},
                "abstract": "",
                "summary": {},
                "filtered_content": content[:500] + "...",
                "recommendations": ["Требуется ручная проверка"]
            }
    
    async def _check_relevance(
        self,
        title: str,
        content: str,
        summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Проверка релевантности и качества контента"""
        prompt = f"""Ты - библиотекарь KB по 3D-печати и диагностике проблем.

Оцени релевантность и качество документа для добавления в KB.

ЗАГОЛОВОК: {title}

СОДЕРЖАНИЕ (первые 2000 символов):
{content[:2000]}

АНАЛИЗ ДОКУМЕНТА:
{json.dumps(summary, ensure_ascii=False, indent=2)[:1000]}

КРИТЕРИИ ОЦЕНКИ:
1. Релевантность тематике 3D-печати (0.0-1.0)
   ✅ РЕЛЕВАНТНЫ:
   - Статьи о проблемах 3D-печати и их решениях
   - Образовательные статьи о 3D-принтерах, материалах, технологиях
   - Документация по оборудованию и настройке
   - Сравнения материалов, принтеров, технологий
   - Технические характеристики и параметры
   - Примеры использования 3D-печати
   - Информация о расходных материалах (филаментах)
   
   ❌ НЕ РЕЛЕВАНТНЫ:
   - Обсуждения музыки, личные предпочтения, оффтоп
   - Контент не связанный с 3D-печатью
   - Чисто развлекательный контент без технической информации

2. Качество информации (конкретность, точность) (0.0-1.0)
   - Для статей о проблемах: есть ли конкретные параметры и решения?
   - Для образовательных статей: структурированность и полнота информации
   - Для документации: точность технических данных
   - Для сравнений: объективность и детальность

3. Наличие полезной информации
   - Решения проблем печати (для статей о проблемах)
   - Технические параметры и характеристики
   - Образовательная ценность (для общих статей)
   - Практическая применимость

4. Отсутствие "воды" и несущественной информации
   - Нет лишних обсуждений
   - Фокус на технической/образовательной информации

ВАЖНО: 
- Образовательные статьи о 3D-печати (например, "Что такое 3D-принтер") РЕЛЕВАНТНЫ и должны получать высокую оценку (>= 0.7)
- Статьи из википедии 3D-печати РЕЛЕВАНТНЫ
- Отклоняй только контент не связанный с 3D-печатью

Верни ТОЛЬКО валидный JSON:
{{
    "score": 0.0-1.0,
    "quality_score": 0.0-1.0,
    "is_relevant": true/false,
    "has_valuable_info": true/false,
    "issues": ["проблема1", "проблема2"] или [],
    "strengths": ["сильная сторона1"] или []
}}
"""
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt="Ты строгий библиотекарь. Оценивай объективно и критично. Отвечай только валидным JSON."
            )
            
            json_data = self._extract_json(response)
            if json_data:
                return json_data
            
        except Exception as e:
            logger.error(f"Ошибка проверки релевантности: {e}", exc_info=True)
        
        # Fallback
        return {
            "score": 0.5,
            "quality_score": 0.5,
            "is_relevant": True,
            "has_valuable_info": True,
            "issues": [],
            "strengths": []
        }
    
    async def _check_duplicates(
        self,
        title: str,
        content: str,
        summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Проверка на дублирование существующих документов в KB"""
        try:
            # Поиск похожих документов в KB
            from app.services.rag_service import get_rag_service
            
            rag_service = get_rag_service()
            
            # Поиск по заголовку и ключевым словам
            search_query = f"{title} {summary.get('problem', '')} {', '.join(summary.get('printer_models', []))}"
            
            similar_docs = await rag_service.search(
                query=search_query,
                limit=5
            )
            
            if not similar_docs:
                return {
                    "is_duplicate": False,
                    "similar_docs": [],
                    "similarity_scores": []
                }
            
            # Анализ похожести через LLM
            similar_titles = [doc.get("title", "") for doc in similar_docs[:3]]
            similar_scores = [doc.get("score", 0.0) for doc in similar_docs[:3]]
            
            prompt = f"""Проверь, является ли новый документ дубликатом существующих в KB.

НОВЫЙ ДОКУМЕНТ:
Заголовок: {title}
Ключевые моменты: {', '.join(summary.get('key_points', [])[:5])}

СУЩЕСТВУЮЩИЕ ДОКУМЕНТЫ В KB:
{chr(10).join(f"{i+1}. {title}" for i, title in enumerate(similar_titles))}

ОЦЕНКИ ПОХОЖЕСТИ (векторный поиск):
{', '.join(f"{score:.2f}" for score in similar_scores)}

ЗАДАЧА:
Определи, является ли новый документ дубликатом или содержит уникальную информацию.

Верни ТОЛЬКО валидный JSON:
{{
    "is_duplicate": true/false,
    "duplicate_reason": "причина" или null,
    "uniqueness": "что уникального в новом документе" или null,
    "recommendation": "approve|reject|merge"
}}
"""
            
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt="Ты библиотекарь. Определяй дубликаты строго. Отвечай только валидным JSON."
            )
            
            json_data = self._extract_json(response)
            
            return {
                "is_duplicate": json_data.get("is_duplicate", False) if json_data else False,
                "duplicate_reason": json_data.get("duplicate_reason") if json_data else None,
                "uniqueness": json_data.get("uniqueness") if json_data else None,
                "recommendation": json_data.get("recommendation", "approve") if json_data else "approve",
                "similar_docs": similar_titles,
                "similarity_scores": similar_scores
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки на дублирование: {e}", exc_info=True)
            return {
                "is_duplicate": False,
                "similar_docs": [],
                "similarity_scores": []
            }
    
    async def _create_abstract(
        self,
        title: str,
        content: str,
        summary: Dict[str, Any]
    ) -> str:
        """Создание качественного abstract без воды"""
        content_type = summary.get("content_type", "article")
        
        # Упрощаем промпт для ускорения обработки
        key_points = summary.get('key_points', [])[:5]  # Ограничиваем до 5 пунктов
        key_points_text = chr(10).join(f"- {kp}" for kp in key_points) if key_points else "Не указаны"
        
        prompt = f"""Создай краткий abstract (2-3 предложения) для статьи:

Заголовок: {title}
Тип: {content_type}
Ключевые моменты:
{key_points_text}

Требования: только факты, без воды, про 3D-печать.

Abstract:"""
        
        try:
            abstract = await self.llm_client.generate(
                prompt=prompt,
                system_prompt="Ты библиотекарь. Создавай краткие и информативные abstract без воды. Только факты."
            )
            
            # Очистка от лишних символов
            abstract = abstract.strip()
            if abstract.startswith('"') and abstract.endswith('"'):
                abstract = abstract[1:-1]
            
            return abstract[:500]  # Ограничение длины
            
        except Exception as e:
            logger.error(f"Ошибка создания abstract: {e}", exc_info=True)
            # Fallback
            return f"{title}. {summary.get('problem', '') or summary.get('summary', '')[:200]}..."
    
    async def _filter_irrelevant_content(
        self,
        content: str,
        summary: Dict[str, Any]
    ) -> str:
        """Фильтрация несущественной информации из контента"""
        prompt = f"""Ты - библиотекарь KB. Отфильтруй несущественную информацию из документа.

ИСХОДНЫЙ КОНТЕНТ:
{content[:3000]}

КЛЮЧЕВЫЕ МОМЕНТЫ (что важно сохранить):
{chr(10).join(f"- {kp}" for kp in summary.get('key_points', [])[:10])}

ЗАДАЧА:
Создай версию контента БЕЗ:
- Воды и общих фраз
- Рекламы и промо-материалов
- Несущественных деталей
- Информации вне тематики 3D-печати

Сохрани ТОЛЬКО:
- Конкретные факты
- Параметры и значения
- Решения и рекомендации
- Технические детали

Отфильтрованный контент:
"""
        
        try:
            filtered = await self.llm_client.generate(
                prompt=prompt,
                system_prompt="Ты библиотекарь. Фильтруй строго. Убирай воду, оставляй только факты."
            )
            
            return filtered[:5000]  # Ограничение длины
            
        except Exception as e:
            logger.error(f"Ошибка фильтрации контента: {e}", exc_info=True)
            return content[:2000] + "..."  # Fallback
    
    async def _make_decision(
        self,
        relevance_check: Dict[str, Any],
        duplicate_check: Dict[str, Any],
        summary: Dict[str, Any],
        abstract: str
    ) -> Dict[str, Any]:
        """Принятие решения о публикации"""
        
        relevance_score = relevance_check.get("score", 0.0)
        quality_score = relevance_check.get("quality_score", 0.0)
        is_relevant = relevance_check.get("is_relevant", False)
        has_valuable_info = relevance_check.get("has_valuable_info", False)
        is_duplicate = duplicate_check.get("is_duplicate", False)
        
        # Критерии принятия
        if is_duplicate:
            return {
                "decision": "reject",
                "reason": f"Документ является дубликатом существующих в KB. {duplicate_check.get('duplicate_reason', '')}",
                "recommendations": [
                    "Проверьте существующие документы в KB",
                    duplicate_check.get("recommendation", "reject") == "merge" and "Рассмотрите возможность объединения" or None
                ]
            }
        
        if not is_relevant or relevance_score < 0.6:
            return {
                "decision": "reject",
                "reason": f"Документ не релевантен тематике KB (score: {relevance_score:.2f}). {', '.join(relevance_check.get('issues', []))}",
                "recommendations": relevance_check.get("issues", [])
            }
        
        if not has_valuable_info or quality_score < 0.6:
            return {
                "decision": "reject",
                "reason": f"Документ не содержит ценной информации (quality: {quality_score:.2f}). {', '.join(relevance_check.get('issues', []))}",
                "recommendations": relevance_check.get("issues", [])
            }
        
        if relevance_score >= 0.7 and quality_score >= 0.7 and not is_duplicate:
            return {
                "decision": "approve",
                "reason": f"Документ релевантен и качественен (relevance: {relevance_score:.2f}, quality: {quality_score:.2f}). {', '.join(relevance_check.get('strengths', []))}",
                "recommendations": ["Готов к публикации в KB"]
            }
        
        # Требуется проверка
        return {
            "decision": "needs_review",
            "reason": f"Требуется ручная проверка (relevance: {relevance_score:.2f}, quality: {quality_score:.2f})",
            "recommendations": [
                "Проверьте релевантность вручную",
                "Убедитесь в отсутствии дублирования",
                *relevance_check.get("issues", [])
            ]
        }
    
    async def analyze_article(
        self,
        title: str,
        content: str,
        images: Optional[List[Dict[str, Any]]] = None,
        url: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Анализ документа и создание краткого изложения
        
        Args:
            title: Заголовок документа
            content: Содержимое документа
            images: Список изображений с описаниями
            url: URL документа
            content_type: Тип контента (article, documentation, comparison, technical)
        
        Returns:
            Краткое изложение с проблемой и решением
        """
        try:
            # Определение типа контента если не указан
            if not content_type:
                content_type = self._detect_content_type(title, content)
            
            # Анализ в зависимости от типа контента
            if content_type == "documentation":
                return await self._analyze_documentation(title, content, images, url)
            elif content_type == "comparison":
                return await self._analyze_comparison(title, content, images, url)
            elif content_type == "technical":
                return await self._analyze_technical(title, content, images, url)
            else:  # article (решение проблем)
                return await self._analyze_problem_article(title, content, images, url)
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа документа: {e}", exc_info=True)
            return self._create_simple_summary(title, content, content_type)
    
    def _detect_content_type(self, title: str, content: str) -> str:
        """Определение типа контента"""
        text = (title + " " + content[:500]).lower()
        
        if any(kw in text for kw in ["документация", "инструкция", "руководство", "manual"]):
            return "documentation"
        elif any(kw in text for kw in ["сравнение", "vs", "versus", "разница"]):
            return "comparison"
        elif any(kw in text for kw in ["характеристики", "параметры", "specs"]):
            return "technical"
        else:
            return "article"
    
    async def _analyze_problem_article(
        self,
        title: str,
        content: str,
        images: Optional[List[Dict[str, Any]]],
        url: Optional[str]
    ) -> Dict[str, Any]:
        """Анализ статьи о решении проблем (оригинальная логика)"""
        text_summary = await self._analyze_text(title, content, content_type="article")
        
        image_analysis = None
        if images:
            image_analysis = await self._analyze_images(images)
        
        summary = await self._create_summary(
            title=title,
            text_analysis=text_summary,
            image_analysis=image_analysis,
            url=url,
            content_type="article"
        )
        
        return summary
    
    async def _analyze_documentation(
        self,
        title: str,
        content: str,
        images: Optional[List[Dict[str, Any]]],
        url: Optional[str]
    ) -> Dict[str, Any]:
        """Анализ документации оборудования"""
        prompt = f"""Ты - умный библиотекарь, специализирующийся на технической документации 3D-принтеров.

Проанализируй документацию и создай краткое изложение.

ЗАГОЛОВОК: {title}

СОДЕРЖАНИЕ:
{content[:4000]}

ЗАДАЧА:
1. Определи тип документации (инструкция, спецификация, руководство)
2. Выдели ключевые характеристики оборудования
3. Перечисли важные параметры и настройки
4. Укажи модели принтеров/оборудования (если есть)

Верни ТОЛЬКО валидный JSON:
{{
    "documentation_type": "instruction" или "specification" или "manual",
    "equipment_models": ["Ender-3", ...] или [],
    "key_specifications": {{
        "parameter1": "значение1",
        "parameter2": "значение2"
    }},
    "important_settings": ["настройка1", "настройка2"],
    "key_points": ["ключевой момент 1", "ключевой момент 2"]
}}
"""
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt="Ты умный библиотекарь. Анализируй документацию структурированно. Отвечай только валидным JSON."
            )
            
            json_data = self._extract_json(response)
            if json_data:
                summary_text = f"""**Тип документации:** {json_data.get('documentation_type', 'unknown')}

**Модели оборудования:**
{chr(10).join(f"- {m}" for m in json_data.get('equipment_models', []))}

**Ключевые характеристики:**
{chr(10).join(f"- {k}: {v}" for k, v in json_data.get('key_specifications', {}).items())}

**Важные настройки:**
{chr(10).join(f"- {s}" for s in json_data.get('important_settings', []))}

**Ключевые моменты:**
{chr(10).join(f"- {kp}" for kp in json_data.get('key_points', []))}
"""
                
                return {
                    "title": title,
                    "url": url,
                    "summary": summary_text,
                    "content_type": "documentation",
                    "documentation_type": json_data.get("documentation_type"),
                    "equipment_models": json_data.get("equipment_models", []),
                    "key_specifications": json_data.get("key_specifications", {}),
                    "important_settings": json_data.get("important_settings", []),
                    "key_points": json_data.get("key_points", [])
                }
        except Exception as e:
            logger.error(f"Ошибка анализа документации: {e}")
        
        return self._create_simple_summary(title, content, "documentation")
    
    async def _analyze_comparison(
        self,
        title: str,
        content: str,
        images: Optional[List[Dict[str, Any]]],
        url: Optional[str]
    ) -> Dict[str, Any]:
        """Анализ сравнения (материалов, принтеров, etc.)"""
        prompt = f"""Ты - умный библиотекарь, специализирующийся на сравнениях в области 3D-печати.

Проанализируй сравнение и создай краткое изложение.

ЗАГОЛОВОК: {title}

СОДЕРЖАНИЕ:
{content[:4000]}

ЗАДАЧА:
1. Определи что сравнивается (материалы, принтеры, настройки)
2. Выдели критерии сравнения
3. Перечисли сравниваемые варианты
4. Укажи ключевые отличия и рекомендации

Верни ТОЛЬКО валидный JSON:
{{
    "comparison_type": "materials" или "printers" или "settings" или "other",
    "compared_items": ["вариант1", "вариант2"],
    "comparison_criteria": ["критерий1", "критерий2"],
    "key_differences": {{
        "вариант1": ["отличие1", "отличие2"],
        "вариант2": ["отличие1", "отличие2"]
    }},
    "recommendations": ["рекомендация1", "рекомендация2"],
    "key_points": ["ключевой момент 1"]
}}
"""
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt="Ты умный библиотекарь. Анализируй сравнения структурированно. Отвечай только валидным JSON."
            )
            
            json_data = self._extract_json(response)
            if json_data:
                summary_text = f"""**Тип сравнения:** {json_data.get('comparison_type', 'unknown')}

**Сравниваемые варианты:**
{chr(10).join(f"- {item}" for item in json_data.get('compared_items', []))}

**Критерии сравнения:**
{chr(10).join(f"- {c}" for c in json_data.get('comparison_criteria', []))}

**Ключевые отличия:**
{chr(10).join(f"- **{item}**: {', '.join(diffs)}" for item, diffs in json_data.get('key_differences', {}).items())}

**Рекомендации:**
{chr(10).join(f"- {r}" for r in json_data.get('recommendations', []))}
"""
                
                return {
                    "title": title,
                    "url": url,
                    "summary": summary_text,
                    "content_type": "comparison",
                    "comparison_type": json_data.get("comparison_type"),
                    "compared_items": json_data.get("compared_items", []),
                    "comparison_criteria": json_data.get("comparison_criteria", []),
                    "key_differences": json_data.get("key_differences", {}),
                    "recommendations": json_data.get("recommendations", []),
                    "key_points": json_data.get("key_points", [])
                }
        except Exception as e:
            logger.error(f"Ошибка анализа сравнения: {e}")
        
        return self._create_simple_summary(title, content, "comparison")
    
    async def _analyze_technical(
        self,
        title: str,
        content: str,
        images: Optional[List[Dict[str, Any]]],
        url: Optional[str]
    ) -> Dict[str, Any]:
        """Анализ технических деталей"""
        prompt = f"""Ты - умный библиотекарь, специализирующийся на технических деталях 3D-печати.

Проанализируй техническую информацию и создай краткое изложение.

ЗАГОЛОВОК: {title}

СОДЕРЖАНИЕ:
{content[:4000]}

ЗАДАЧА:
1. Определи тему (материалы, технологии, параметры печати)
2. Выдели ключевые технические характеристики
3. Перечисли важные параметры и их значения
4. Укажи области применения

Верни ТОЛЬКО валидный JSON:
{{
    "topic": "материалы" или "технологии" или "параметры",
    "key_characteristics": {{
        "характеристика1": "значение1",
        "характеристика2": "значение2"
    }},
    "important_parameters": ["параметр1", "параметр2"],
    "applications": ["применение1", "применение2"],
    "key_points": ["ключевой момент 1"]
}}
"""
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt="Ты умный библиотекарь. Анализируй техническую информацию структурированно. Отвечай только валидным JSON."
            )
            
            json_data = self._extract_json(response)
            if json_data:
                summary_text = f"""**Тема:** {json_data.get('topic', 'unknown')}

**Ключевые характеристики:**
{chr(10).join(f"- {k}: {v}" for k, v in json_data.get('key_characteristics', {}).items())}

**Важные параметры:**
{chr(10).join(f"- {p}" for p in json_data.get('important_parameters', []))}

**Области применения:**
{chr(10).join(f"- {a}" for a in json_data.get('applications', []))}
"""
                
                return {
                    "title": title,
                    "url": url,
                    "summary": summary_text,
                    "content_type": "technical",
                    "topic": json_data.get("topic"),
                    "key_characteristics": json_data.get("key_characteristics", {}),
                    "important_parameters": json_data.get("important_parameters", []),
                    "applications": json_data.get("applications", []),
                    "key_points": json_data.get("key_points", [])
                }
        except Exception as e:
            logger.error(f"Ошибка анализа технической информации: {e}")
        
        return self._create_simple_summary(title, content, "technical")
    
    async def _analyze_text(self, title: str, content: str, content_type: str = "article") -> Dict[str, Any]:
        """Анализ текста документа (базовая логика)"""
        prompt = f"""Ты - умный библиотекарь, специализирующийся на статьях о 3D-печати.

Проанализируй статью и создай краткое изложение.

ЗАГОЛОВОК: {title}

СОДЕРЖАНИЕ:
{content[:4000]}

ЗАДАЧА:
1. Определи основную проблему, о которой идет речь
2. Выдели ключевые симптомы
3. Перечисли конкретные решения с параметрами
4. Укажи модели принтеров и материалы (если упоминаются)

Верни ТОЛЬКО валидный JSON без дополнительного текста:
{{
    "problem": "Краткое описание проблемы (1-2 предложения)",
    "symptoms": ["симптом1", "симптом2"],
    "solutions": [
        {{
            "description": "Краткое описание решения",
            "parameters": {{
                "parameter1": "значение1",
                "parameter2": "значение2"
            }}
        }}
    ],
    "printer_models": ["Ender-3"] или [],
    "materials": ["PLA"] или [],
    "key_points": ["ключевой момент 1", "ключевой момент 2"]
}}
"""
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt="Ты умный библиотекарь. Анализируй статьи структурированно и точно. Отвечай только валидным JSON."
            )
            
            return self._extract_json(response) or self._extract_simple_analysis(title, content)
                
        except Exception as e:
            logger.error(f"Ошибка анализа текста: {e}")
            return self._extract_simple_analysis(title, content)
    
    def _extract_json(self, response: str) -> Optional[Dict[str, Any]]:
        """Извлечение JSON из ответа LLM"""
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except:
            pass
        return None
    
    async def _analyze_images(self, images: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Анализ изображений из статьи через Gemini Vision API
        Адаптировано из ai_billing проекта
        """
        if not images:
            return None
        
        try:
            # Импортируем VisionAnalyzer
            from app.services.vision_analyzer import VisionAnalyzer
            
            # Определяем, какой провайдер использовать для анализа изображений
            # Если основной провайдер - ollama, предпочитаем llava
            prefer_ollama = (self.llm_provider or os.getenv("LLM_PROVIDER", "")).lower() == "ollama"
            vision_analyzer = VisionAnalyzer(prefer_ollama=prefer_ollama)
            
            # Проверяем доступность Vision API (Gemini или Ollama/llava)
            availability = vision_analyzer.check_availability()
            if not availability.get('available', False):
                logger.warning(f"⚠️ Vision API недоступен ({availability.get('provider', 'unknown')}): {availability.get('message', 'Unknown')}")
                # Fallback на анализ описаний
                return await self._analyze_images_fallback(images)
            
            logger.info(f"📷 Используется {availability.get('provider', 'unknown')} для анализа изображений")
            
            # Анализируем каждое изображение через Gemini Vision API
            image_analyses = []
            relevant_images = []
            
            for img_idx, img in enumerate(images[:10]):  # Ограничиваем до 10 изображений
                try:
                    # Пытаемся получить base64 данные изображения
                    image_data = img.get("data")
                    image_path = img.get("url")
                    image_name = img.get("title") or img.get("alt") or f"image_{img_idx + 1}"
                    
                    analysis_result = None
                    
                    # Если есть base64 данные, анализируем их
                    if image_data:
                        try:
                            analysis_result = vision_analyzer.analyze_image_from_base64(image_data, image_name)
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка анализа base64 изображения {image_name}: {e}")
                    
                    # Если есть путь к файлу, анализируем его
                    elif image_path and Path(image_path).exists():
                        try:
                            analysis_result = vision_analyzer.analyze_image_from_path(Path(image_path))
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка анализа файла {image_path}: {e}")
                    
                    # Если анализ успешен, проверяем релевантность
                    if analysis_result and analysis_result.get('success'):
                        analysis_text = analysis_result.get('analysis', '')
                        
                        # Проверяем релевантность к 3D-печати
                        relevance_result = vision_analyzer.check_relevance_to_3d_printing(analysis_text, image_name)
                        
                        if relevance_result.get('success') and relevance_result.get('is_relevant', False):
                            relevant_images.append({
                                'image_name': image_name,
                                'analysis': analysis_text,
                                'relevance_score': relevance_result.get('relevance_score', 0.5),
                                'problem_type': relevance_result.get('problem_type'),
                                'printer_models': relevance_result.get('printer_models', []),
                                'materials': relevance_result.get('materials', [])
                            })
                            logger.info(f"✅ Изображение {image_name} релевантно 3D-печати (score={relevance_result.get('relevance_score', 0.5):.2f})")
                        else:
                            logger.info(f"ℹ️ Изображение {image_name} не релевантно 3D-печати")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка обработки изображения {img_idx + 1}: {e}")
                    continue
            
            # Формируем результат анализа
            if relevant_images:
                # Объединяем информацию из всех релевантных изображений
                all_problems = []
                all_solutions = []
                all_printer_models = set()
                all_materials = set()
                
                for img_data in relevant_images:
                    if img_data.get('problem_type'):
                        all_problems.append(img_data['problem_type'])
                    if img_data.get('printer_models'):
                        all_printer_models.update(img_data['printer_models'])
                    if img_data.get('materials'):
                        all_materials.update(img_data['materials'])
                
                return {
                    "problems_shown": list(set(all_problems)),
                    "solutions_shown": all_solutions,  # Можно расширить логикой определения решений
                    "visual_indicators": [img['image_name'] for img in relevant_images],
                    "relevant_images_count": len(relevant_images),
                    "total_images_analyzed": len(images),
                    "printer_models": list(all_printer_models),
                    "materials": list(all_materials),
                    "image_analyses": relevant_images
                }
            else:
                logger.info("ℹ️ Релевантные изображения не найдены")
                return None
                
        except ImportError as e:
            logger.warning(f"⚠️ VisionAnalyzer недоступен: {e}, используем fallback")
            return await self._analyze_images_fallback(images)
        except Exception as e:
            logger.error(f"❌ Ошибка анализа изображений через Gemini Vision: {e}")
            # Fallback на анализ описаний
            return await self._analyze_images_fallback(images)
    
    async def _analyze_images_fallback(self, images: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Fallback метод: анализ изображений по описаниям (старый метод)"""
        image_descriptions = [img.get("description", "") or img.get("alt", "") for img in images]
        image_descriptions = [desc for desc in image_descriptions if desc]
        
        if not image_descriptions:
            return None
        
        prompt = f"""Проанализируй описания изображений из статьи о 3D-печати.

ОПИСАНИЯ ИЗОБРАЖЕНИЙ:
{chr(10).join(f"- {desc}" for desc in image_descriptions[:10])}

ЗАДАЧА:
Определи, какие проблемы или решения показаны на изображениях.

Верни ТОЛЬКО валидный JSON:
{{
    "problems_shown": ["проблема1", "проблема2"] или [],
    "solutions_shown": ["решение1"] или [],
    "visual_indicators": ["индикатор1"] или []
}}
"""
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt="Анализируй описания изображений. Отвечай только валидным JSON."
            )
            
            return self._extract_json(response)
        except Exception as e:
            logger.error(f"Ошибка анализа изображений (fallback): {e}")
        
        return None
    
    async def _create_summary(
        self,
        title: str,
        text_analysis: Dict[str, Any],
        image_analysis: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        content_type: str = "article"
    ) -> Dict[str, Any]:
        """Создание итогового изложения"""
        
        problem = text_analysis.get("problem", "")
        if image_analysis and image_analysis.get("problems_shown"):
            image_problems = ", ".join(image_analysis["problems_shown"])
            if image_problems:
                problem += f" (на изображениях показано: {image_problems})"
        
        solutions = text_analysis.get("solutions", [])
        if image_analysis and image_analysis.get("solutions_shown"):
            for img_solution in image_analysis["solutions_shown"]:
                solutions.append({
                    "description": f"Показано на изображении: {img_solution}",
                    "parameters": {}
                })
        
        summary_text = f"""**Проблема:** {problem}

**Симптомы:**
{chr(10).join(f"- {s}" for s in text_analysis.get("symptoms", []))}

**Решения:**
{chr(10).join(f"- {sol.get('description', '')}" + (f" (параметры: {sol.get('parameters', {})})" if sol.get('parameters') else "") for sol in solutions)}

**Ключевые моменты:**
{chr(10).join(f"- {kp}" for kp in text_analysis.get("key_points", []))}
"""
        
        return {
            "title": title,
            "url": url,
            "summary": summary_text,
            "problem": problem,
            "symptoms": text_analysis.get("symptoms", []),
            "solutions": solutions,
            "printer_models": text_analysis.get("printer_models", []),
            "materials": text_analysis.get("materials", []),
            "key_points": text_analysis.get("key_points", []),
            "image_analysis": image_analysis,
            "content_type": content_type
        }
    
    def _extract_simple_analysis(self, title: str, content: str) -> Dict[str, Any]:
        """Простое извлечение анализа без LLM"""
        content_lower = content.lower()
        
        problem_keywords = {
            "stringing": ["stringing", "сопли", "ниточки"],
            "warping": ["warping", "коробление", "отслоение"],
            "layer_separation": ["расслоение", "трещины", "слои"]
        }
        
        detected_problem = None
        for problem, keywords in problem_keywords.items():
            if any(kw in content_lower for kw in keywords):
                detected_problem = problem
                break
        
        return {
            "problem": detected_problem or "Проблема не определена",
            "symptoms": [],
            "solutions": [],
            "printer_models": [],
            "materials": [],
            "key_points": []
        }
    
    def _create_simple_summary(self, title: str, content: str, content_type: str = "article") -> Dict[str, Any]:
        """Простое изложение без анализа"""
        return {
            "title": title,
            "summary": f"**Документ:** {title}\n\n{content[:500]}...",
            "content_type": content_type,
            "problem": "Не определена",
            "symptoms": [],
            "solutions": [],
            "printer_models": [],
            "materials": [],
            "key_points": []
        }
