"""
RAG сервис для поиска в базе знаний
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / "config.env")

logger = logging.getLogger(__name__)


class RAGService:
    """
    Сервис для RAG (Retrieval Augmented Generation)
    """
    
    def __init__(self):
        """Инициализация RAG сервиса"""
        self.embedding_model = None
        self._initialize_embedding_model()
    
    def _initialize_embedding_model(self):
        """Инициализация модели эмбеддингов"""
        try:
            import torch
            from sentence_transformers import SentenceTransformer
            
            model_name = os.getenv("HF_MODEL_NAME", "intfloat/multilingual-e5-base")
            
            # Определяем устройство (CPU если CUDA недоступна или переполнена)
            device = "cpu"
            if torch.cuda.is_available():
                try:
                    # Пробуем использовать CUDA, но если памяти мало - используем CPU
                    torch.cuda.empty_cache()
                    device = "cuda"
                except Exception:
                    device = "cpu"
            
            logger.info(f"Загрузка модели эмбеддингов: {model_name} на {device}")
            self.embedding_model = SentenceTransformer(model_name, device=device)
            logger.info(f"✅ Модель эмбеддингов загружена: {model_name} на {device}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки модели эмбеддингов: {e}")
            # Fallback на CPU
            try:
                logger.info("Попытка загрузки на CPU...")
                self.embedding_model = SentenceTransformer(model_name, device="cpu")
                logger.info(f"✅ Модель загружена на CPU")
            except Exception as e2:
                logger.error(f"❌ Критическая ошибка: {e2}")
                raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Генерация эмбеддинга для текста
        
        Args:
            text: Текст для генерации эмбеддинга
        
        Returns:
            Список чисел (эмбеддинг)
        """
        try:
            embedding = self.embedding_model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"❌ Ошибка генерации эмбеддинга: {e}")
            raise
    
    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        is_image: bool = False,
        score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Гибридный поиск в базе знаний (векторный + фильтры по метаданным)
        
        Args:
            query: Текстовый запрос
            filters: Фильтры по метаданным (problem_type, printer_models, materials)
            limit: Максимальное количество результатов
            is_image: True если поиск по изображениям
            score_threshold: Минимальный порог релевантности (0.0 - 1.0)
        
        Returns:
            Список найденных статей с метаданными, отсортированных по релевантности
        """
        try:
            from app.services.vector_db import get_vector_db
            
            # Генерация эмбеддинга запроса
            query_embedding = self.generate_embedding(query)
            
            # Поиск в векторной БД (гибридный: векторный + фильтры)
            db = get_vector_db()
            results = await db.search(
                query_embedding=query_embedding,
                filters=filters,
                limit=limit * 2,  # Получаем больше результатов для фильтрации по score
                is_image=is_image
            )
            
            # Фильтрация по порогу релевантности и сортировка
            filtered_results = [
                r for r in results 
                if r.get("score", 0.0) >= score_threshold
            ]
            
            # Сортировка по релевантности (по убыванию)
            filtered_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            
            # Ограничение количества результатов
            final_results = filtered_results[:limit]
            
            logger.info(
                f"✅ Найдено результатов: {len(final_results)} "
                f"(из {len(results)} после фильтрации по score>={score_threshold})"
            )
            return final_results
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска в RAG: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def hybrid_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        boost_filters: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Расширенный гибридный поиск с бустингом результатов по фильтрам
        
        Args:
            query: Текстовый запрос
            filters: Фильтры по метаданным
            limit: Максимальное количество результатов
            boost_filters: Увеличивать ли релевантность результатов, соответствующих фильтрам
        
        Returns:
            Список найденных статей с улучшенными оценками релевантности
        """
        # Базовый поиск
        results = await self.search(
            query=query,
            filters=filters,
            limit=limit * 2 if boost_filters else limit,
            score_threshold=0.3  # Базовый порог
        )
        
        if not boost_filters or not filters:
            return results[:limit]
        
        # Бустинг результатов, соответствующих фильтрам
        boosted_results = []
        for result in results:
            score = result.get("score", 0.0)
            
            # Проверка соответствия фильтрам
            matches_filters = True
            boost = 0.0
            
            if filters.get("problem_type") and result.get("problem_type") == filters["problem_type"]:
                boost += 0.1
            
            if filters.get("printer_models"):
                result_printers = result.get("printer_models", [])
                if any(p in result_printers for p in filters["printer_models"]):
                    boost += 0.1
            
            if filters.get("materials"):
                result_materials = result.get("materials", [])
                if any(m in result_materials for m in filters["materials"]):
                    boost += 0.1
            
            # Применяем буст
            if boost > 0:
                result["score"] = min(score + boost, 1.0)  # Ограничиваем максимумом 1.0
                result["boost_applied"] = boost
            
            boosted_results.append(result)
        
        # Повторная сортировка с учетом буста
        boosted_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        
        logger.info(f"✅ Гибридный поиск: применен буст к {sum(1 for r in boosted_results if r.get('boost_applied', 0) > 0)} результатам")
        
        return boosted_results[:limit]


# Singleton instance
_rag_service_instance: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Получить экземпляр RAG сервиса (singleton)"""
    global _rag_service_instance
    
    if _rag_service_instance is None:
        _rag_service_instance = RAGService()
    
    return _rag_service_instance

