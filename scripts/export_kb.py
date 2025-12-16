#!/usr/bin/env python3
"""
Скрипт для экспорта базы знаний из Qdrant в JSON файлы
Использование: python scripts/export_kb.py [output_dir]
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / "config.env")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import ScrollRequest
except ImportError:
    print("❌ Ошибка: установите qdrant-client: pip install qdrant-client")
    sys.exit(1)


def export_kb(output_dir: str = "knowledge_base/export") -> None:
    """
    Экспорт всех статей из Qdrant в JSON файлы
    
    Args:
        output_dir: Директория для сохранения экспортированных файлов
    """
    # Инициализация клиента Qdrant
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    collection_name = os.getenv("QDRANT_COLLECTION", "kb_3dtoday")
    image_collection_name = os.getenv("QDRANT_IMAGE_COLLECTION", "kb_3dtoday_images")
    
    try:
        client = QdrantClient(host=host, port=port)
        print(f"✅ Подключение к Qdrant: {host}:{port}")
    except Exception as e:
        print(f"❌ Ошибка подключения к Qdrant: {e}")
        sys.exit(1)
    
    # Создаем директорию для экспорта
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Экспорт текстовых статей
    print(f"\n📚 Экспорт текстовых статей из коллекции '{collection_name}'...")
    articles = []
    
    try:
        # Получаем все точки из коллекции
        scroll_result = client.scroll(
            collection_name=collection_name,
            limit=100,
            with_payload=True,
            with_vectors=False
        )
        
        points = scroll_result[0]
        offset = scroll_result[1]
        
        while points:
            for point in points:
                payload = point.payload or {}
                article = {
                    "id": str(point.id),
                    "title": payload.get("title", "Без названия"),
                    "content": payload.get("content", ""),
                    "url": payload.get("url", ""),
                    "section": payload.get("section", ""),
                    "problem_type": payload.get("problem_type", ""),
                    "printer_models": payload.get("printer_models", []),
                    "materials": payload.get("materials", []),
                    "symptoms": payload.get("symptoms", []),
                    "solutions": payload.get("solutions", []),
                    "abstract": payload.get("abstract", ""),
                    "relevance_score": payload.get("relevance_score", 0.0),
                    "quality_score": payload.get("quality_score", 0.0),
                    "content_type": payload.get("content_type", "article"),
                    "tags": payload.get("tags", []),
                    "date": payload.get("date", ""),
                    "author": payload.get("author", ""),
                    "images": payload.get("images", [])
                }
                articles.append(article)
            
            if offset:
                scroll_result = client.scroll(
                    collection_name=collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )
                points = scroll_result[0]
                offset = scroll_result[1]
            else:
                break
        
        print(f"✅ Найдено статей: {len(articles)}")
        
        # Сохраняем в JSON файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        articles_file = output_path / f"articles_{timestamp}.json"
        
        with open(articles_file, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Статьи сохранены в: {articles_file}")
        
    except Exception as e:
        print(f"❌ Ошибка экспорта статей: {e}")
        import traceback
        traceback.print_exc()
    
    # Экспорт изображений
    print(f"\n🖼️  Экспорт изображений из коллекции '{image_collection_name}'...")
    images = []
    
    try:
        scroll_result = client.scroll(
            collection_name=image_collection_name,
            limit=100,
            with_payload=True,
            with_vectors=False
        )
        
        points = scroll_result[0]
        offset = scroll_result[1]
        
        while points:
            for point in points:
                payload = point.payload or {}
                image = {
                    "id": str(point.id),
                    "url": payload.get("url", ""),
                    "alt": payload.get("alt", ""),
                    "description": payload.get("description", ""),
                    "article_id": payload.get("article_id", ""),
                    "article_title": payload.get("article_title", ""),
                    "relevance_score": payload.get("relevance_score", 0.0),
                    "problem_type": payload.get("problem_type", ""),
                    "tags": payload.get("tags", [])
                }
                images.append(image)
            
            if offset:
                scroll_result = client.scroll(
                    collection_name=image_collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )
                points = scroll_result[0]
                offset = scroll_result[1]
            else:
                break
        
        print(f"✅ Найдено изображений: {len(images)}")
        
        # Сохраняем в JSON файл
        images_file = output_path / f"images_{timestamp}.json"
        
        with open(images_file, "w", encoding="utf-8") as f:
            json.dump(images, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Изображения сохранены в: {images_file}")
        
    except Exception as e:
        print(f"⚠️  Ошибка экспорта изображений (возможно коллекция не существует): {e}")
    
    # Создаем файл с метаданными экспорта
    metadata = {
        "export_date": datetime.now().isoformat(),
        "articles_count": len(articles),
        "images_count": len(images),
        "collection_name": collection_name,
        "image_collection_name": image_collection_name,
        "qdrant_host": host,
        "qdrant_port": port
    }
    
    metadata_file = output_path / f"export_metadata_{timestamp}.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Экспорт завершен!")
    print(f"📁 Файлы сохранены в: {output_path}")
    print(f"   - Статьи: {articles_file.name}")
    print(f"   - Изображения: {images_file.name}")
    print(f"   - Метаданные: {metadata_file.name}")


if __name__ == "__main__":
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "knowledge_base/export"
    export_kb(output_dir)

