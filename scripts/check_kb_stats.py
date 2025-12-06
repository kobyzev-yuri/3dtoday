#!/usr/bin/env python3
"""
Скрипт для проверки статистики KB
"""

import httpx
import json
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def check_api_stats():
    """Проверка статистики через API"""
    try:
        response = httpx.get("http://localhost:8000/api/kb/statistics", timeout=10)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        print("❌ Ошибка: FastAPI не запущен")
        print("💡 Запустите: ./scripts/start_fastapi.sh")
        return None
    except Exception as e:
        print(f"❌ Ошибка API: {e}")
        return None

def check_direct_stats():
    """Проверка статистики напрямую через Qdrant"""
    try:
        from backend.app.services.vector_db import get_vector_db
        
        db = get_vector_db()
        stats = db.get_statistics()
        
        # Статистика изображений
        try:
            image_collection_info = db.client.get_collection(db.image_collection_name)
            image_count = image_collection_info.points_count
        except Exception:
            image_count = 0
        
        return {
            "text_articles": stats.get("articles_count", 0),
            "images": image_count,
            "total_vectors": stats.get("vectors_count", 0) + image_count
        }
    except Exception as e:
        print(f"❌ Ошибка прямого доступа: {e}")
        return None

def main():
    print("📊 Проверка статистики KB\n")
    print("=" * 50)
    
    # Пробуем через API
    stats = check_api_stats()
    
    if not stats:
        # Если API не доступен, пробуем напрямую
        print("\n⚠️  API недоступен, пробую прямой доступ к Qdrant...")
        stats = check_direct_stats()
    
    if stats:
        print("\n✅ Статистика базы знаний:")
        print(f"  • Статей: {stats.get('text_articles', 0)}")
        print(f"  • Изображений: {stats.get('images', 0)}")
        print(f"  • Всего векторов: {stats.get('total_vectors', 0)}")
        
        if stats.get('indexed_vectors'):
            print(f"  • Проиндексировано: {stats.get('indexed_vectors', 0)}")
        
        return 0
    else:
        print("\n❌ Не удалось получить статистику")
        return 1

if __name__ == "__main__":
    sys.exit(main())

