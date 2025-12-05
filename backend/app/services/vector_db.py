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
        self.image_collection_name = os.getenv("QDRANT_IMAGE_COLLECTION", "kb_3dtoday_images")
        self.embedding_dim = int(os.getenv("EMBEDDING_DIMENSION", "768"))  # Для текста
        self.image_embedding_dim = int(os.getenv("IMAGE_EMBEDDING_DIMENSION", "512"))  # Для изображений (OpenCLIP)
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
            
            # Создание коллекций, если не существуют
            self._ensure_collection()  # Текстовая коллекция
            self._ensure_image_collection()  # Коллекция для изображений
            
            logger.info(f"✅ Qdrant клиент инициализирован (host={host}, port={port})")
            logger.info(f"   Коллекция текста: {self.collection_name} (dim={self.embedding_dim})")
            logger.info(f"   Коллекция изображений: {self.image_collection_name} (dim={self.image_embedding_dim})")
            
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
        """Создание коллекции для текста, если она не существует"""
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
                logger.info(f"✅ Создана коллекция: {self.collection_name} (dim={self.embedding_dim})")
            else:
                logger.info(f"✅ Коллекция уже существует: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания коллекции: {e}")
            raise
    
    def _ensure_image_collection(self):
        """Создание коллекции для изображений, если она не существует"""
        try:
            from qdrant_client.models import Distance, VectorParams
            
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.image_collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.image_collection_name,
                    vectors_config=VectorParams(
                        size=self.image_embedding_dim,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"✅ Создана коллекция изображений: {self.image_collection_name} (dim={self.image_embedding_dim})")
            else:
                logger.info(f"✅ Коллекция изображений уже существует: {self.image_collection_name}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания коллекции изображений: {e}")
            raise
    
    async def add_article(
        self,
        article: Dict[str, Any],
        embedding: List[float],
        is_image: bool = False
    ) -> bool:
        """
        Добавление статьи в векторную БД
        
        Args:
            article: Словарь с данными статьи
            embedding: Векторное представление статьи
            is_image: True если это изображение (используется коллекция для изображений)
        
        Returns:
            True если успешно
        """
        try:
            from qdrant_client.models import PointStruct
            
            # Определяем коллекцию и размерность
            collection = self.image_collection_name if is_image else self.collection_name
            expected_dim = self.image_embedding_dim if is_image else self.embedding_dim
            
            # Проверка размерности
            if len(embedding) != expected_dim:
                logger.error(
                    f"❌ Несоответствие размерности: ожидается {expected_dim}, получено {len(embedding)}"
                )
                return False
            
            # Qdrant требует числовой ID или UUID
            # Генерируем числовой ID из article_id или url
            article_id_str = article.get("article_id") or article.get("url", "")
            
            # Используем hash для генерации числового ID
            # Преобразуем в положительное число
            point_id = abs(hash(article_id_str)) % (2**63)  # Максимальный int64
            
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    **article,
                    "original_id": article_id_str,  # Сохраняем оригинальный ID в payload
                    "content_type": "image" if is_image else "article"
                }
            )
            
            self.client.upsert(
                collection_name=collection,
                points=[point]
            )
            
            content_type = "изображение" if is_image else "статья"
            logger.info(f"✅ {content_type.capitalize()} добавлена: {article.get('title', 'unknown')} (ID: {point_id})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления статьи: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def search(
        self,
        query_embedding: List[float],
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        is_image: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Поиск статей по векторному запросу
        
        Args:
            query_embedding: Векторное представление запроса
            filters: Фильтры по метаданным (опционально)
            limit: Максимальное количество результатов
            is_image: True если поиск по изображениям
        
        Returns:
            Список найденных статей с метаданными
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            # Определяем коллекцию
            collection = self.image_collection_name if is_image else self.collection_name
            
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
            
            # Поиск через query_points (универсальный метод)
            response = self.client.query_points(
                collection_name=collection,
                query=query_embedding,  # Вектор запроса
                query_filter=qdrant_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            
            # Форматирование результатов
            articles = []
            for point in response.points:
                article = point.payload.copy() if point.payload else {}
                article["score"] = point.score if hasattr(point, 'score') else 0.0
                articles.append(article)
            
            content_type = "изображений" if is_image else "статей"
            logger.info(f"✅ Найдено {content_type}: {len(articles)}")
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            import traceback
            traceback.print_exc()
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

