"""
Продвинутый Retrieval Agent для поиска в KB
С поддержкой реранкинга и контекста изображений
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / "config.env")

logger = logging.getLogger(__name__)


class RetrievalAgent:
    """
    Продвинутый агент для поиска в базе знаний
    с поддержкой реранкинга и контекста изображений
    """
    
    def __init__(self):
        """Инициализация Retrieval Agent"""
        self.rag_service = None
        self.reranker_model = None
        self.vision_analyzer = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Инициализация сервисов"""
        try:
            from app.services.rag_service import get_rag_service
            self.rag_service = get_rag_service()
            logger.info("✅ RAG Service инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации RAG Service: {e}")
            raise
        
        # Инициализация реранкера (опционально)
        self._initialize_reranker()
        
        # Инициализация Vision Analyzer для анализа изображений
        try:
            from app.services.vision_analyzer import VisionAnalyzer
            self.vision_analyzer = VisionAnalyzer(prefer_ollama=False)
            logger.info("✅ Vision Analyzer инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Vision Analyzer не доступен: {e}")
            self.vision_analyzer = None
    
    def _initialize_reranker(self):
        """Инициализация Cross-Encoder модели для реранкинга"""
        try:
            from sentence_transformers import CrossEncoder
            
            # Модель для реранкинга (легкая и быстрая)
            reranker_model_name = os.getenv(
                "RERANKER_MODEL", 
                "cross-encoder/ms-marco-MiniLM-L-12-v2"
            )
            
            logger.info(f"Загрузка модели реранкинга: {reranker_model_name}")
            self.reranker_model = CrossEncoder(reranker_model_name)
            logger.info(f"✅ Модель реранкинга загружена: {reranker_model_name}")
            
        except ImportError:
            logger.warning("⚠️ sentence-transformers не установлен, реранкинг отключен")
            self.reranker_model = None
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки модели реранкинга: {e}, реранкинг отключен")
            self.reranker_model = None
    
    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        vision_context: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        use_reranking: bool = True,
        rerank_top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Продвинутый поиск в KB с поддержкой реранкинга и контекста изображений
        
        Args:
            query: Текстовый запрос
            filters: Фильтры по метаданным (problem_type, printer_models, materials)
            vision_context: Контекст из анализа изображения (problem_type, symptoms, description)
            limit: Количество результатов для возврата
            use_reranking: Использовать ли реранкинг
            rerank_top_k: Количество кандидатов для реранкинга
            
        Returns:
            Список найденных статей с метаданными, отсортированных по релевантности
        """
        try:
            # 1. Улучшение запроса с учетом контекста изображения
            enhanced_query = self._enhance_query_with_vision_context(query, vision_context)
            
            # 2. Обновление фильтров с учетом vision_context
            enhanced_filters = self._enhance_filters_with_vision_context(filters, vision_context)
            
            # 3. Первичный поиск в KB (получаем больше кандидатов для реранкинга)
            initial_limit = rerank_top_k if use_reranking and self.reranker_model else limit
            initial_results = await self.rag_service.hybrid_search(
                query=enhanced_query,
                filters=enhanced_filters,
                limit=initial_limit,
                boost_filters=True
            )
            
            if not initial_results:
                logger.warning("⚠️ Не найдено результатов в KB")
                return []
            
            # 4. Дедупликация результатов по article_id или url
            seen_ids = set()
            seen_urls = set()
            deduplicated_results = []
            
            for result in initial_results:
                article_id = result.get('article_id') or result.get('original_id')
                url = result.get('url')
                
                # Проверяем уникальность по ID или URL
                is_duplicate = False
                if article_id and article_id in seen_ids:
                    is_duplicate = True
                elif url and url in seen_urls:
                    is_duplicate = True
                
                if not is_duplicate:
                    deduplicated_results.append(result)
                    if article_id:
                        seen_ids.add(article_id)
                    if url:
                        seen_urls.add(url)
            
            logger.info(f"🔍 Дедупликация: {len(initial_results)} -> {len(deduplicated_results)} уникальных результатов")
            
            # 5. Реранкинг результатов (если включен и модель доступна)
            if use_reranking and self.reranker_model and len(deduplicated_results) > 1:
                reranked_results = self._rerank_results(
                    query=enhanced_query,
                    results=deduplicated_results,
                    top_k=limit
                )
                logger.info(f"✅ Реранкинг применен к {len(deduplicated_results)} результатам")
                return reranked_results
            else:
                # Без реранкинга просто возвращаем топ-K
                return deduplicated_results[:limit]
                
        except Exception as e:
            logger.error(f"❌ Ошибка поиска в RetrievalAgent: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _enhance_query_with_vision_context(
        self, 
        query: str, 
        vision_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Улучшение запроса с учетом контекста изображения
        
        Args:
            query: Исходный запрос
            vision_context: Контекст из анализа изображения
            
        Returns:
            Улучшенный запрос
        """
        if not vision_context:
            return query
        
        enhanced_parts = [query]
        
        # Добавляем описание из анализа изображения
        if vision_context.get("description"):
            enhanced_parts.append(vision_context["description"])
        
        # Добавляем симптомы
        if vision_context.get("symptoms"):
            symptoms = vision_context["symptoms"]
            if isinstance(symptoms, list):
                enhanced_parts.append(" ".join(symptoms))
            else:
                enhanced_parts.append(str(symptoms))
        
        enhanced_query = " ".join(enhanced_parts)
        logger.debug(f"Улучшенный запрос: {enhanced_query[:200]}...")
        
        return enhanced_query
    
    def _enhance_filters_with_vision_context(
        self,
        filters: Optional[Dict[str, Any]],
        vision_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Обновление фильтров с учетом контекста изображения
        
        Args:
            filters: Исходные фильтры
            vision_context: Контекст из анализа изображения
            
        Returns:
            Обновленные фильтры
        """
        if not vision_context:
            return filters or {}
        
        enhanced_filters = filters.copy() if filters else {}
        
        # Добавляем problem_type из vision_context, если его нет в фильтрах
        if vision_context.get("problem_type") and not enhanced_filters.get("problem_type"):
            enhanced_filters["problem_type"] = vision_context["problem_type"]
            logger.debug(f"Добавлен фильтр problem_type: {vision_context['problem_type']}")
        
        return enhanced_filters
    
    def _rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Реранкинг результатов с помощью Cross-Encoder
        
        Args:
            query: Текстовый запрос
            results: Список результатов для реранкинга
            top_k: Количество топ результатов для возврата
            
        Returns:
            Переранжированные результаты
        """
        if not self.reranker_model or not results:
            return results
        
        try:
            # Формируем пары (запрос, статья) для оценки
            pairs = []
            for result in results:
                # Используем title и content для оценки релевантности
                article_text = f"{result.get('title', '')} {result.get('content', '')[:500]}"
                pairs.append([query, article_text])
            
            # Получаем оценки релевантности от Cross-Encoder
            scores = self.reranker_model.predict(pairs)
            
            # Обновляем score результатов
            for i, result in enumerate(results):
                # Комбинируем оригинальный score и score от реранкера
                original_score = result.get("score", 0.0)
                rerank_score = float(scores[i])
                
                # Нормализуем rerank_score (Cross-Encoder возвращает logits)
                # Используем sigmoid для нормализации в диапазон [0, 1]
                try:
                    import numpy as np
                    normalized_rerank_score = 1 / (1 + np.exp(-rerank_score))
                except ImportError:
                    # Fallback без numpy (простая нормализация)
                    normalized_rerank_score = max(0.0, min(1.0, (rerank_score + 5) / 10))
                
                # Комбинируем scores (можно настроить веса)
                # 0.4 * original + 0.6 * rerank (больше веса реранкеру)
                combined_score = 0.4 * original_score + 0.6 * normalized_rerank_score
                
                result["score"] = combined_score
                result["rerank_score"] = normalized_rerank_score
                result["original_score"] = original_score
            
            # Сортировка по новому score
            reranked_results = sorted(
                results,
                key=lambda x: x.get("score", 0.0),
                reverse=True
            )
            
            logger.info(
                f"✅ Реранкинг завершен: "
                f"топ-{top_k} из {len(results)} результатов"
            )
            
            return reranked_results[:top_k]
            
        except Exception as e:
            logger.error(f"❌ Ошибка реранкинга: {e}")
            import traceback
            traceback.print_exc()
            # В случае ошибки возвращаем оригинальные результаты
            return results[:top_k]
    
    async def search_with_image(
        self,
        query: str,
        image_data: Optional[bytes] = None,
        image_path: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        use_reranking: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Поиск с анализом изображения для извлечения контекста
        
        Args:
            query: Текстовый запрос
            image_data: Байты изображения
            image_path: Путь к файлу изображения
            filters: Фильтры по метаданным
            limit: Количество результатов
            use_reranking: Использовать ли реранкинг
            
        Returns:
            Список найденных статей
        """
        vision_context = None
        
        # Анализ изображения, если предоставлено
        if image_data or image_path:
            if not self.vision_analyzer:
                logger.warning("⚠️ Vision Analyzer недоступен, поиск без анализа изображения")
            else:
                try:
                    if image_data:
                        vision_result = self.vision_analyzer.analyze_image(image_data)
                    elif image_path:
                        vision_result = self.vision_analyzer.analyze_image_from_path(
                            Path(image_path)
                        )
                    else:
                        vision_result = None
                    
                    if vision_result and vision_result.get("success"):
                        # Получаем текст анализа
                        analysis_text = vision_result.get("analysis") or vision_result.get("description", "")
                        
                        # Извлекаем структурированные данные из текста анализа
                        # Пробуем извлечь problem_type из текста (простой поиск ключевых слов)
                        problem_type = vision_result.get("problem_type")
                        if not problem_type and analysis_text:
                            analysis_lower = analysis_text.lower()
                            if "stringing" in analysis_lower or "сопли" in analysis_lower or "ниточки" in analysis_lower:
                                problem_type = "stringing"
                            elif "warping" in analysis_lower or "коробление" in analysis_lower:
                                problem_type = "warping"
                            elif "layer" in analysis_lower and ("separation" in analysis_lower or "расслоение" in analysis_lower):
                                problem_type = "layer_separation"
                            elif "bed" in analysis_lower and ("adhesion" in analysis_lower or "адгезия" in analysis_lower):
                                problem_type = "bed_adhesion"
                        
                        # Извлекаем симптомы из текста
                        symptoms = vision_result.get("symptoms", [])
                        if not symptoms and analysis_text:
                            # Простой поиск ключевых слов симптомов
                            symptom_keywords = ["ниточки", "сопли", "паутина", "коробление", "расслоение", "отслоение"]
                            found_symptoms = [kw for kw in symptom_keywords if kw in analysis_text.lower()]
                            if found_symptoms:
                                symptoms = found_symptoms
                        
                        vision_context = {
                            "problem_type": problem_type,
                            "symptoms": symptoms,
                            "description": analysis_text
                        }
                        logger.info(f"✅ Изображение проанализировано: problem_type={problem_type}, symptoms={len(symptoms)}")
                    else:
                        logger.warning("⚠️ Не удалось проанализировать изображение")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка анализа изображения: {e}")
        
        # Поиск с учетом контекста изображения
        return await self.search(
            query=query,
            filters=filters,
            vision_context=vision_context,
            limit=limit,
            use_reranking=use_reranking
        )


# Singleton instance
_retrieval_agent_instance: Optional[RetrievalAgent] = None


def get_retrieval_agent() -> RetrievalAgent:
    """Получить экземпляр Retrieval Agent (singleton)"""
    global _retrieval_agent_instance
    
    if _retrieval_agent_instance is None:
        _retrieval_agent_instance = RetrievalAgent()
    
    return _retrieval_agent_instance


def reset_retrieval_agent():
    """Сбросить singleton (для тестирования)"""
    global _retrieval_agent_instance
    _retrieval_agent_instance = None

