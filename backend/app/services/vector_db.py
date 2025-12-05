"""
Клиент для работы с векторной БД (Qdrant)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / "config.env")

logger = logging.getLogger(__name__)


class VectorDBService:
    """
    Сервис для работы с векторной БД Qdrant
    """
    
    def __init__(self):
        """Инициализация клиента Qdrant"""
        self.db_type = os.getenv("VECTOR_DB_TYPE", "qdrant").lower()
        self.client = None
        self.collection_name = os.getenv("QDRANT_COLLECTION", "kb_3dtoday")
        self.embedding_dim = int(os.getenv("EMBEDDING_DIMENSION", "768"))
        self._initialize_client()
    
    def _initialize_client(self):
        """Инициализация клиента в зависимости от типа БД"""
        if self.db_type == "qdrant":
            self._init_qdrant()
        else:
            raise ValueError(f"Неподдерживаемый тип векторной БД: {self.db_type}")
    
    def _init_qdrant(self):
        """Инициализация Qdrant клиента"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            
            host = os.getenv("QDRANT_HOST", "localhost")
            port = int(os.getenv("QDRANT_PORT", "6333"))
            
            self.client = QdrantClient(host=host, port=port)
            
            # Проверка подключения
            self._check_connection()
            
            # Создание коллекции, если не существует
            self._ensure_collection()
            
            logger.info(f"✅ Qdrant клиент инициализирован (host={host}, port={port}, collection={self.collection_name})")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Qdrant: {e}")
            raise
    
    def _check_connection(self):
        """Проверка подключения к Qdrant"""
        try:
            collections = self.client.get_collections()
            logger.info(f"✅ Подключение к Qdrant успешно (найдено коллекций: {len(collections.collections)})")
        except Exception as e:
            logger.error(f"❌ Не удалось подключиться к Qdrant: {e}")
            logger.error("💡 Запустите Qdrant:")
            logger.error("   ./scripts/start_qdrant.sh")
            logger.error("   или: docker-compose up -d qdrant")
            raise
    
    def _ensure_collection(self):
        """Создание коллекции, если она не существует"""
        try:
            from qdrant_client.models import Distance, VectorParams
            
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_dim,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"✅ Создана коллекция: {self.collection_name}")
            else:
                logger.info(f"✅ Коллекция уже существует: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания коллекции: {e}")
            raise
    
    async def add_article(
        self,
        article: Dict[str, Any],
        embedding: List[float]
    ) -> bool:
        """
        Добавление статьи в векторную БД
        
        Args:
            article: Словарь с данными статьи
            embedding: Векторное представление статьи
        
        Returns:
            True если успешно
        """
        try:
            from qdrant_client.models import PointStruct
            
            point = PointStruct(
                id=article.get("article_id") or hash(article.get("url", "")),
                vector=embedding,
                payload=article
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.info(f"✅ Статья добавлена: {article.get('title', 'unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления статьи: {e}")
            return False
    
    async def search(
        self,
        query_embedding: List[float],
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Поиск статей по векторному запросу
        
        Args:
            query_embedding: Векторное представление запроса
            filters: Фильтры по метаданным (опционально)
            limit: Максимальное количество результатов
        
        Returns:
            Список найденных статей с метаданными
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            # Построение фильтров
            qdrant_filter = None
            if filters:
                conditions = []
                
                if "problem_type" in filters:
                    conditions.append(
                        FieldCondition(
                            key="problem_type",
                            match=MatchValue(value=filters["problem_type"])
                        )
                    )
                
                if "printer_models" in filters:
                    conditions.append(
                        FieldCondition(
                            key="printer_models",
                            match=MatchValue(value=filters["printer_models"])
                        )
                    )
                
                if "materials" in filters:
                    conditions.append(
                        FieldCondition(
                            key="materials",
                            match=MatchValue(value=filters["materials"])
                        )
                    )
                
                if conditions:
                    qdrant_filter = Filter(must=conditions)
            
            # Поиск
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=qdrant_filter,
                limit=limit
            )
            
            # Форматирование результатов
            articles = []
            for result in results:
                article = result.payload.copy()
                article["score"] = result.score
                articles.append(article)
            
            logger.info(f"✅ Найдено статей: {len(articles)}")
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return []
    
    async def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение статьи по ID
        
        Args:
            article_id: ID статьи
        
        Returns:
            Данные статьи или None
        """
        try:
            from qdrant_client.models import PointId
            
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[article_id]
            )
            
            if result:
                return result[0].payload
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статьи: {e}")
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики KB
        
        Returns:
            Словарь со статистикой
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)
            
            return {
                "articles_count": collection_info.points_count,
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {}


# Singleton instance
_vector_db_instance: Optional[VectorDBService] = None


def get_vector_db() -> VectorDBService:
    """Получить экземпляр VectorDB сервиса (singleton)"""
    global _vector_db_instance
    
    if _vector_db_instance is None:
        _vector_db_instance = VectorDBService()
    
    return _vector_db_instance

