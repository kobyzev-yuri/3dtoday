#!/usr/bin/env python3
"""
Скрипт для проверки статистики KB с детальной информацией
"""

import httpx
import json
import sys
from pathlib import Path
from collections import Counter
from typing import Dict, Any, List

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

def get_detailed_stats() -> Dict[str, Any]:
    """Получение детальной статистики из Qdrant"""
    try:
        from backend.app.services.vector_db import get_vector_db
        from qdrant_client.models import ScrollRequest
        
        db = get_vector_db()
        
        # Получаем все статьи
        scroll_result = db.client.scroll(
            collection_name=db.collection_name,
            limit=1000,
            with_payload=True,
            with_vectors=False
        )
        
        points = scroll_result[0]
        articles = [point.payload for point in points]
        
        # Собираем статистику
        problem_types = Counter()
        printer_models = Counter()
        materials = Counter()
        sections = Counter()
        content_types = Counter()
        
        articles_with_solutions = 0
        articles_with_images = 0
        
        for article in articles:
            # Проблемы
            if article.get("problem_type"):
                problem_types[article["problem_type"]] += 1
            
            # Принтеры
            if article.get("printer_models"):
                for printer in article["printer_models"]:
                    printer_models[printer] += 1
            
            # Материалы
            if article.get("materials"):
                for material in article["materials"]:
                    materials[material] += 1
            
            # Разделы
            if article.get("section"):
                sections[article["section"]] += 1
            
            # Типы контента
            if article.get("content_type"):
                content_types[article["content_type"]] += 1
            
            # Решения
            if article.get("solutions"):
                articles_with_solutions += 1
            
            # Изображения
            if article.get("images"):
                articles_with_images += 1
        
        # Статистика изображений
        try:
            image_collection_info = db.client.get_collection(db.image_collection_name)
            image_count = image_collection_info.points_count
        except Exception:
            image_count = 0
        
        return {
            "total_articles": len(articles),
            "images": image_count,
            "problem_types": dict(problem_types.most_common(10)),
            "printer_models": dict(printer_models.most_common(10)),
            "materials": dict(materials.most_common(10)),
            "sections": dict(sections.most_common(10)),
            "content_types": dict(content_types),
            "articles_with_solutions": articles_with_solutions,
            "articles_with_images": articles_with_images
        }
    except Exception as e:
        print(f"⚠️  Ошибка получения детальной статистики: {e}")
        return None

def main():
    print("📊 Проверка статистики KB\n")
    print("=" * 60)
    
    # Базовая статистика
    stats = check_api_stats()
    
    if not stats:
        # Если API не доступен, пробуем напрямую
        print("\n⚠️  API недоступен, пробую прямой доступ к Qdrant...")
        stats = check_direct_stats()
    
    if stats:
        print("\n✅ Базовая статистика:")
        print(f"  • Статей: {stats.get('text_articles', 0)}")
        print(f"  • Изображений: {stats.get('images', 0)}")
        print(f"  • Всего векторов: {stats.get('total_vectors', 0)}")
        
        if stats.get('indexed_vectors'):
            print(f"  • Проиндексировано: {stats.get('indexed_vectors', 0)}")
    
    # Детальная статистика
    print("\n" + "=" * 60)
    print("📈 Детальная статистика\n")
    
    detailed = get_detailed_stats()
    
    if detailed:
        print(f"📚 Всего статей: {detailed['total_articles']}")
        print(f"🖼️  Изображений в коллекции: {detailed['images']}")
        print(f"✅ Статей с решениями: {detailed['articles_with_solutions']}")
        print(f"📷 Статей с изображениями: {detailed['articles_with_images']}")
        
        if detailed.get('problem_types'):
            print("\n🔧 Типы проблем:")
            for problem, count in detailed['problem_types'].items():
                print(f"   • {problem}: {count}")
        
        if detailed.get('printer_models'):
            print("\n🖨️  Модели принтеров:")
            for printer, count in detailed['printer_models'].items():
                print(f"   • {printer}: {count}")
        
        if detailed.get('materials'):
            print("\n🧪 Материалы:")
            for material, count in detailed['materials'].items():
                print(f"   • {material}: {count}")
        
        if detailed.get('sections'):
            print("\n📂 Разделы:")
            for section, count in detailed['sections'].items():
                print(f"   • {section}: {count}")
        
        if detailed.get('content_types'):
            print("\n📄 Типы контента:")
            for content_type, count in detailed['content_types'].items():
                print(f"   • {content_type}: {count}")
    
    print("\n" + "=" * 60)
    
    if stats or detailed:
        return 0
    else:
        print("\n❌ Не удалось получить статистику")
        return 1

if __name__ == "__main__":
    sys.exit(main())


