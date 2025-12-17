#!/usr/bin/env python3
"""
Скрипт для импорта базы знаний из JSON файлов экспорта в Qdrant
Использование: python scripts/import_kb.py [articles_file] [images_file]
Пример: python scripts/import_kb.py knowledge_base/export/articles_20251217_000422.json
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / "config.env")

try:
    from backend.app.services.article_indexer import ArticleIndexer
except ImportError:
    # Альтернативный путь
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "app"))
    from services.article_indexer import ArticleIndexer


async def import_articles(articles_file: str, skip_existing: bool = True) -> Dict[str, Any]:
    """
    Импорт статей из JSON файла
    
    Args:
        articles_file: Путь к JSON файлу со статьями
        skip_existing: Пропускать ли существующие статьи (по article_id)
    
    Returns:
        Статистика импорта
    """
    if not Path(articles_file).exists():
        print(f"❌ Файл не найден: {articles_file}")
        return {"success": False, "error": "File not found"}
    
    print(f"📚 Загрузка статей из: {articles_file}")
    
    try:
        with open(articles_file, "r", encoding="utf-8") as f:
            articles = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return {"success": False, "error": str(e)}
    
    if not isinstance(articles, list):
        print(f"❌ Неверный формат файла: ожидается массив статей")
        return {"success": False, "error": "Invalid format"}
    
    print(f"✅ Загружено статей: {len(articles)}")
    
    # Инициализация индексатора
    try:
        indexer = ArticleIndexer()
        print("✅ ArticleIndexer инициализирован")
    except Exception as e:
        print(f"❌ Ошибка инициализации ArticleIndexer: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
    
    # Статистика
    stats = {
        "total": len(articles),
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "error_details": []
    }
    
    # Импорт статей
    print(f"\n🔄 Начало импорта {len(articles)} статей...")
    
    for idx, article in enumerate(articles, 1):
        try:
            # Подготовка данных статьи
            article_data = {
                "article_id": article.get("id") or article.get("article_id") or f"imported_{abs(hash(article.get('title', '')))}",
                "title": article.get("title", "Без названия"),
                "content": article.get("content", ""),
                "url": article.get("url", ""),
                "section": article.get("section", ""),
                "problem_type": article.get("problem_type", ""),
                "printer_models": article.get("printer_models", []),
                "materials": article.get("materials", []),
                "symptoms": article.get("symptoms", []),
                "solutions": article.get("solutions", []),
                "abstract": article.get("abstract", ""),
                "relevance_score": article.get("relevance_score", 1.0),
                "quality_score": article.get("quality_score", 0.0),
                "content_type": article.get("content_type", "article"),
                "tags": article.get("tags", []),
                "date": article.get("date", ""),
                "author": article.get("author", "")
            }
            
            # Валидация обязательных полей
            if not article_data["title"] or not article_data["content"]:
                print(f"⚠️  Статья {idx}: пропущена (нет title или content)")
                stats["skipped"] += 1
                continue
            
            # Индексация статьи
            result = await indexer.index_article(article_data, generate_embedding=True)
            
            if result.get("success"):
                stats["imported"] += 1
                if idx % 10 == 0:
                    print(f"   ✅ Импортировано: {stats['imported']}/{idx} статей")
            else:
                error_msg = result.get("error", "Unknown error")
                print(f"⚠️  Статья {idx} ({article_data['title'][:50]}...): {error_msg}")
                stats["errors"] += 1
                stats["error_details"].append({
                    "article_id": article_data["article_id"],
                    "title": article_data["title"],
                    "error": error_msg
                })
        
        except Exception as e:
            print(f"❌ Ошибка импорта статьи {idx}: {e}")
            stats["errors"] += 1
            stats["error_details"].append({
                "article_id": article.get("id", "unknown"),
                "title": article.get("title", "unknown"),
                "error": str(e)
            })
    
    print(f"\n✅ Импорт статей завершен!")
    print(f"   📊 Всего: {stats['total']}")
    print(f"   ✅ Импортировано: {stats['imported']}")
    print(f"   ⏭️  Пропущено: {stats['skipped']}")
    print(f"   ❌ Ошибок: {stats['errors']}")
    
    if stats["errors"] > 0:
        print(f"\n⚠️  Детали ошибок:")
        for detail in stats["error_details"][:10]:  # Показываем первые 10
            print(f"   - {detail['title'][:50]}: {detail['error']}")
        if len(stats["error_details"]) > 10:
            print(f"   ... и еще {len(stats['error_details']) - 10} ошибок")
    
    return {"success": True, "stats": stats}


async def import_images(images_file: str) -> Dict[str, Any]:
    """
    Импорт изображений из JSON файла
    
    Args:
        images_file: Путь к JSON файлу с изображениями
    
    Returns:
        Статистика импорта
    """
    if not Path(images_file).exists():
        print(f"⚠️  Файл изображений не найден: {images_file}")
        return {"success": False, "error": "File not found", "skipped": True}
    
    print(f"\n🖼️  Загрузка изображений из: {images_file}")
    
    try:
        with open(images_file, "r", encoding="utf-8") as f:
            images = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return {"success": False, "error": str(e)}
    
    if not isinstance(images, list):
        print(f"❌ Неверный формат файла: ожидается массив изображений")
        return {"success": False, "error": "Invalid format"}
    
    print(f"✅ Загружено изображений: {len(images)}")
    print(f"⚠️  Импорт изображений требует наличия файлов изображений")
    print(f"   Для полного импорта изображений используйте административный интерфейс")
    
    # Статистика
    stats = {
        "total": len(images),
        "imported": 0,
        "skipped": len(images),  # Пока пропускаем все, т.к. нужны файлы
        "errors": 0
    }
    
    print(f"\n⚠️  Импорт изображений пропущен (требуются файлы изображений)")
    print(f"   Используйте административный интерфейс для загрузки изображений")
    
    return {"success": True, "stats": stats, "skipped": True}


async def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("Использование: python scripts/import_kb.py <articles_file> [images_file]")
        print("\nПримеры:")
        print("  python scripts/import_kb.py knowledge_base/export/articles_20251217_000422.json")
        print("  python scripts/import_kb.py articles.json images.json")
        sys.exit(1)
    
    articles_file = sys.argv[1]
    images_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("=" * 60)
    print("📦 ИМПОРТ БАЗЫ ЗНАНИЙ (KB)")
    print("=" * 60)
    
    # Проверка Qdrant
    try:
        from qdrant_client import QdrantClient
        host = os.getenv("QDRANT_HOST", "localhost")
        port = int(os.getenv("QDRANT_PORT", "6333"))
        client = QdrantClient(host=host, port=port)
        print(f"✅ Подключение к Qdrant: {host}:{port}")
    except Exception as e:
        print(f"❌ Ошибка подключения к Qdrant: {e}")
        print("   Убедитесь, что Qdrant запущен: ./scripts/start_qdrant.sh")
        sys.exit(1)
    
    # Импорт статей
    articles_result = await import_articles(articles_file)
    
    # Импорт изображений (если указан файл)
    images_result = None
    if images_file:
        images_result = await import_images(images_file)
    else:
        # Пытаемся найти файл изображений рядом со статьями
        articles_path = Path(articles_file)
        images_path = articles_path.parent / articles_path.name.replace("articles_", "images_")
        if images_path.exists():
            print(f"\n🔍 Найден файл изображений: {images_path}")
            response = input("   Импортировать изображения? (y/n): ").strip().lower()
            if response == "y":
                images_result = await import_images(str(images_path))
    
    # Итоговая статистика
    print("\n" + "=" * 60)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 60)
    
    if articles_result.get("success"):
        stats = articles_result.get("stats", {})
        print(f"📚 Статьи:")
        print(f"   ✅ Импортировано: {stats.get('imported', 0)}/{stats.get('total', 0)}")
        print(f"   ❌ Ошибок: {stats.get('errors', 0)}")
    
    if images_result and not images_result.get("skipped"):
        stats = images_result.get("stats", {})
        print(f"🖼️  Изображения:")
        print(f"   ✅ Импортировано: {stats.get('imported', 0)}/{stats.get('total', 0)}")
    elif images_result and images_result.get("skipped"):
        print(f"🖼️  Изображения: пропущены (требуются файлы)")
    
    print("\n✅ Импорт завершен!")
    print("   Проверьте KB через: curl http://localhost:8000/api/kb/statistics")


if __name__ == "__main__":
    asyncio.run(main())

