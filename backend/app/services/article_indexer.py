"""
Сервис для индексации статей в базу знаний
"""

import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / "config.env")

logger = logging.getLogger(__name__)


class ArticleIndexer:
    """
    Сервис для индексации статей в векторную БД
    """
    
    def __init__(self):
        """Инициализация индексатора"""
        self.rag_service = None
        self.vector_db = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Инициализация зависимых сервисов"""
        try:
            from services.rag_service import get_rag_service
            from services.vector_db import get_vector_db
            
            self.rag_service = get_rag_service()
            self.vector_db = get_vector_db()
            
            logger.info("✅ ArticleIndexer инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации ArticleIndexer: {e}")
            raise
    
    async def index_article(
        self,
        article: Dict[str, Any],
        generate_embedding: bool = True
    ) -> Dict[str, Any]:
        """
        Индексация статьи в векторную БД
        
        Args:
            article: Словарь с данными статьи:
                - article_id: уникальный ID статьи
                - title: заголовок
                - content: содержимое
                - url: URL статьи (опционально)
                - problem_type: тип проблемы (опционально)
                - printer_models: список моделей принтеров (опционально)
                - materials: список материалов (опционально)
                - symptoms: список симптомов (опционально)
                - solutions: список решений (опционально)
            generate_embedding: Генерировать ли эмбеддинг автоматически
        
        Returns:
            Результат индексации с ID и статусом
        """
        try:
            # Валидация обязательных полей
            if not article.get("article_id"):
                raise ValueError("article_id обязателен")
            if not article.get("title"):
                raise ValueError("title обязателен")
            if not article.get("content"):
                raise ValueError("content обязателен")
            
            # Генерация эмбеддинга
            if generate_embedding:
                text_for_embedding = f"{article['title']} {article['content']}"
                embedding = self.rag_service.generate_embedding(text_for_embedding)
            else:
                # Если эмбеддинг уже есть в статье
                embedding = article.get("embedding")
                if not embedding:
                    raise ValueError("embedding обязателен, если generate_embedding=False")
            
            # Подготовка данных для Qdrant
            article_data = {
                "article_id": article["article_id"],
                "title": article["title"],
                "content": article["content"],
                "url": article.get("url", ""),
                "problem_type": article.get("problem_type"),
                "printer_models": article.get("printer_models", []),
                "materials": article.get("materials", []),
                "symptoms": article.get("symptoms", []),
                "solutions": article.get("solutions", []),
                "section": article.get("section", ""),
                "date": article.get("date", ""),
                "relevance_score": article.get("relevance_score", 1.0)
            }
            
            # Добавление в Qdrant
            success = await self.vector_db.add_article(
                article=article_data,
                embedding=embedding,
                is_image=False
            )
            
            if success:
                logger.info(f"✅ Статья '{article['title']}' успешно проиндексирована")
                return {
                    "success": True,
                    "article_id": article["article_id"],
                    "title": article["title"],
                    "embedding_dim": len(embedding)
                }
            else:
                logger.error(f"❌ Не удалось проиндексировать статью '{article['title']}'")
                return {
                    "success": False,
                    "article_id": article["article_id"],
                    "error": "Failed to add article to vector DB"
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка индексации статьи: {e}", exc_info=True)
            return {
                "success": False,
                "article_id": article.get("article_id", "unknown"),
                "error": str(e)
            }
    
    async def index_image(
        self,
        image_data: Dict[str, Any],
        image_path: str,
        generate_embedding: bool = True
    ) -> Dict[str, Any]:
        """
        Индексация изображения в векторную БД
        
        Args:
            image_data: Метаданные изображения:
                - article_id: уникальный ID
                - title: описание изображения
                - content: текстовое описание (опционально)
                - problem_type: тип проблемы
                - printer_models: список моделей принтеров
                - materials: список материалов
            image_path: Путь к файлу изображения
            generate_embedding: Генерировать ли эмбеддинг автоматически
        
        Returns:
            Результат индексации
        """
        try:
            from services.openclip_embeddings import get_openclip_embeddings
            
            # Валидация
            if not image_data.get("article_id"):
                raise ValueError("article_id обязателен")
            if not image_path or not Path(image_path).exists():
                raise ValueError(f"Изображение не найдено: {image_path}")
            
            # Генерация эмбеддинга изображения
            if generate_embedding:
                clip_model = get_openclip_embeddings(
                    model_name=os.getenv("OPENCLIP_MODEL", "ViT-B-16"),
                    pretrained=os.getenv("OPENCLIP_PRETRAINED", "openai")
                )
                embedding = clip_model.encode_image(image_path)
            else:
                embedding = image_data.get("embedding")
                if not embedding:
                    raise ValueError("embedding обязателен, если generate_embedding=False")
            
            # Подготовка данных
            article_data = {
                "article_id": image_data["article_id"],
                "title": image_data.get("title", "Изображение дефекта"),
                "content": image_data.get("content", ""),
                "image_path": str(image_path),
                "problem_type": image_data.get("problem_type"),
                "printer_models": image_data.get("printer_models", []),
                "materials": image_data.get("materials", []),
                "symptoms": image_data.get("symptoms", []),
                "content_type": "image"
            }
            
            # Добавление в Qdrant (коллекция изображений)
            success = await self.vector_db.add_article(
                article=article_data,
                embedding=embedding,
                is_image=True
            )
            
            if success:
                logger.info(f"✅ Изображение '{image_data['article_id']}' успешно проиндексировано")
                return {
                    "success": True,
                    "article_id": image_data["article_id"],
                    "embedding_dim": len(embedding)
                }
            else:
                return {
                    "success": False,
                    "article_id": image_data["article_id"],
                    "error": "Failed to add image to vector DB"
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка индексации изображения: {e}", exc_info=True)
            return {
                "success": False,
                "article_id": image_data.get("article_id", "unknown"),
                "error": str(e)
            }
    
    async def batch_index_articles(
        self,
        articles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Пакетная индексация статей
        
        Args:
            articles: Список статей для индексации
        
        Returns:
            Статистика индексации
        """
        results = {
            "total": len(articles),
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        for article in articles:
            result = await self.index_article(article)
            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({
                    "article_id": article.get("article_id", "unknown"),
                    "error": result.get("error", "Unknown error")
                })
        
        logger.info(f"✅ Пакетная индексация завершена: {results['success']}/{results['total']} успешно")
        return results


# Singleton instance
_article_indexer_instance: Optional[ArticleIndexer] = None


def get_article_indexer() -> ArticleIndexer:
    """Получить экземпляр ArticleIndexer (singleton)"""
    global _article_indexer_instance
    
    if _article_indexer_instance is None:
        _article_indexer_instance = ArticleIndexer()
    
    return _article_indexer_instance

