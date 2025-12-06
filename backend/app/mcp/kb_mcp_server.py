#!/usr/bin/env python3
"""
KB MCP Server для проекта 3dtoday
Предоставляет инструменты для работы с базой знаний через MCP протокол
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

# Добавляем путь к модулям проекта
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
from mcp.server.fastmcp.prompts.base import Message

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание MCP сервера
mcp = FastMCP("KB3DToday")


# ========== TOOLS ==========

@mcp.tool()
def search_kb_articles(
    query: str,
    problem_type: Optional[str] = None,
    printer_model: Optional[str] = None,
    material: Optional[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Поиск статей в KB по запросу с фильтрацией по метаданным.
    
    Args:
        query: Текстовый запрос для поиска
        problem_type: Тип проблемы (stringing, warping, layer_separation, etc.)
        printer_model: Модель принтера (Ender-3, Anycubic Kobra, etc.)
        material: Материал (PLA, PETG, ABS, etc.)
        limit: Максимальное количество результатов (по умолчанию 5)
    
    Returns:
        Словарь с найденными статьями и их метаданными
    """
    try:
        import asyncio
        from app.services.rag_service import get_rag_service
        
        rag_service = get_rag_service()
        
        # Построение фильтров
        filters = {}
        if problem_type:
            filters["problem_type"] = problem_type
        if printer_model:
            filters["printer_models"] = [printer_model]
        if material:
            filters["materials"] = [material]
        
        # Поиск в KB (синхронный вызов async функции)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если цикл уже запущен, создаем новый поток
                import concurrent.futures
                import threading
                
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            rag_service.search(query, filters=filters, limit=limit)
                        )
                    finally:
                        new_loop.close()
                
                mcp_timeout = int(os.getenv("MCP_SERVER_TIMEOUT", "180"))
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    results = future.result(timeout=mcp_timeout)
            else:
                results = loop.run_until_complete(
                    rag_service.search(query, filters=filters, limit=limit)
                )
        except RuntimeError:
            # Нет event loop, создаем новый
            results = asyncio.run(
                rag_service.search(query, filters=filters, limit=limit)
            )
        
        # Форматирование результатов
        articles = []
        for r in results:
            article = {
                "article_id": r.get("article_id") or r.get("original_id", "unknown"),
                "title": r.get("title", "Без названия"),
                "content": r.get("content", "")[:500] + "..." if len(r.get("content", "")) > 500 else r.get("content", ""),
                "relevance_score": round(r.get("score", 0.0), 3),
                "problem_type": r.get("problem_type"),
                "printer_models": r.get("printer_models", []),
                "materials": r.get("materials", []),
                "symptoms": r.get("symptoms", []),
                "solutions": r.get("solutions", [])
            }
            articles.append(article)
        
        logger.info(f"✅ Найдено статей: {len(articles)}")
        
        return {
            "articles": articles,
            "count": len(articles),
            "query": query,
            "filters": filters
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска статей: {e}", exc_info=True)
        return {
            "error": str(e),
            "articles": [],
            "count": 0
        }


@mcp.tool()
def get_article_by_id(article_id: str) -> Dict[str, Any]:
    """
    Получить полную статью по ID.
    
    Args:
        article_id: ID статьи в KB (может быть article_id или original_id)
    
    Returns:
        Полная информация о статье или ошибка, если статья не найдена
    """
    try:
        from app.services.vector_db import get_vector_db
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        db = get_vector_db()
        
        # Поиск статьи по ID через scroll (синхронный метод Qdrant)
        # Пробуем найти по article_id или original_id
        filter_conditions = [
            FieldCondition(
                key="article_id",
                match=MatchValue(value=article_id)
            )
        ]
        
        qdrant_filter = Filter(must=filter_conditions)
        
        # Используем scroll для поиска по фильтру
        result = db.client.scroll(
            collection_name=db.collection_name,
            scroll_filter=qdrant_filter,
            limit=1,
            with_payload=True,
            with_vectors=False
        )
        
        if result[0] and len(result[0]) > 0:
            point = result[0][0]
            article = point.payload
            
            return {
                "article_id": article.get("article_id") or article.get("original_id", "unknown"),
                "title": article.get("title", "Без названия"),
                "content": article.get("content", ""),
                "url": article.get("url"),
                "problem_type": article.get("problem_type"),
                "printer_models": article.get("printer_models", []),
                "materials": article.get("materials", []),
                "symptoms": article.get("symptoms", []),
                "solutions": article.get("solutions", []),
                "section": article.get("section"),
                "date": article.get("date"),
                "relevance_score": article.get("relevance_score")
            }
        else:
            return {
                "error": f"Статья с ID '{article_id}' не найдена в KB",
                "article_id": article_id
            }
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статьи: {e}", exc_info=True)
        return {
            "error": str(e),
            "article_id": article_id
        }


@mcp.tool()
def parse_document(
    source: str,
    source_type: Optional[str] = None,
    llm_provider: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[int] = None
) -> Dict[str, Any]:
    """
    Парсинг документа из разных источников и анализ через агента-библиотекаря.
    
    Поддерживает:
    - HTML/URL: статьи с сайтов (например, 3dtoday.ru)
    - PDF: документация оборудования, инструкции
    - JSON: импорт существующих блоков KB в стандартном формате
    
    Типы контента:
    - article: решение проблем 3D-печати
    - documentation: документация оборудования
    - comparison: сравнения материалов/принтеров
    - technical: технические детали и характеристики
    
    Args:
        source: URL, путь к файлу, или JSON строка
        source_type: Тип источника (auto, html, pdf, json, url). Если не указан, определяется автоматически
    
    Returns:
        Распарсенный документ с кратким изложением от агента-библиотекаря
    """
    try:
        import asyncio
        from app.services.document_parser import DocumentParser
        from app.agents.kb_librarian import KBLibrarianAgent
        
        parser = DocumentParser()
        # Используем провайдер из параметров или из config.env
        # Если не указан, будет использован из config.env (по умолчанию ollama)
        librarian = KBLibrarianAgent(
            llm_provider=llm_provider,
            model=model,
            timeout=timeout
        )
        
        # Парсинг документа
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    doc_data = new_loop.run_until_complete(
                        parser.parse_document(source, source_type)
                    )
                    if not doc_data:
                        return None
                    
                    # Полный цикл: анализ + решение о публикации
                    review_result = new_loop.run_until_complete(
                        librarian.review_and_decide(
                            title=doc_data["title"],
                            content=doc_data["content"],
                            images=doc_data.get("images", []),
                            url=doc_data.get("url"),
                            content_type=doc_data.get("content_type"),
                            is_questions_list=doc_data.get("is_questions_list", False)
                        )
                    )
                    return {"document": doc_data, "review": review_result}
                finally:
                    new_loop.close()
            
            mcp_timeout = int(os.getenv("MCP_SERVER_TIMEOUT", "180"))
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                result = future.result(timeout=mcp_timeout)
        else:
            doc_data = loop.run_until_complete(
                parser.parse_document(source, source_type)
            )
            if not doc_data:
                return {"error": "Не удалось распарсить документ", "source": source[:100]}
            
            # Полный цикл: анализ + решение о публикации
            review_result = loop.run_until_complete(
                librarian.review_and_decide(
                    title=doc_data["title"],
                    content=doc_data["content"],
                    images=doc_data.get("images", []),
                    url=doc_data.get("url"),
                    content_type=doc_data.get("content_type"),
                    is_questions_list=doc_data.get("is_questions_list", False)
                )
            )
            result = {"document": doc_data, "review": review_result}
        
        if result:
            doc = result["document"]
            review = result["review"]
            summ = review.get("summary", {})
            
            response = {
                "success": True,
                "source": source[:100] if len(source) > 100 else source,
                "source_type": doc.get("content_type", "unknown"),
                "title": doc["title"],
                "section": doc.get("section", "unknown"),
                "decision": review.get("decision", "needs_review"),
                "reason": review.get("reason", ""),
                "relevance_score": review.get("relevance_score", 0.0),
                "quality_score": review.get("quality_score", 0.0),
                "abstract": review.get("abstract", ""),
                "summary": summ.get("summary", ""),
                "content_type": summ.get("content_type", doc.get("content_type", "article")),
                "duplicate_check": review.get("duplicate_check", {}),
                "recommendations": review.get("recommendations", [])
            }
            
            # Добавляем специфичные поля в зависимости от типа контента
            content_type = summ.get("content_type", "article")
            
            if content_type == "article":
                response.update({
                    "problem": summ.get("problem", ""),
                    "symptoms": summ.get("symptoms", []),
                    "solutions": summ.get("solutions", []),
                    "printer_models": summ.get("printer_models", []),
                    "materials": summ.get("materials", [])
                })
            elif content_type == "documentation":
                response.update({
                    "documentation_type": summ.get("documentation_type"),
                    "equipment_models": summ.get("equipment_models", []),
                    "key_specifications": summ.get("key_specifications", {})
                })
            elif content_type == "comparison":
                response.update({
                    "comparison_type": summ.get("comparison_type"),
                    "compared_items": summ.get("compared_items", []),
                    "key_differences": summ.get("key_differences", {})
                })
            elif content_type == "technical":
                response.update({
                    "topic": summ.get("topic"),
                    "key_characteristics": summ.get("key_characteristics", {})
                })
            
            response["images_count"] = len(doc.get("images", []))
            
            return response
        else:
            return {"error": "Не удалось распарсить документ", "source": source[:100]}
            
    except Exception as e:
        logger.error(f"❌ Ошибка парсинга документа: {e}", exc_info=True)
        return {
            "error": str(e),
            "source": source[:100] if len(source) > 100 else source
        }


@mcp.tool()
def get_kb_statistics() -> Dict[str, Any]:
    """
    Получить статистику базы знаний.
    
    Returns:
        Словарь со статистикой KB (количество статей, изображений, покрытие проблем)
    """
    try:
        from app.services.vector_db import get_vector_db
        
        db = get_vector_db()
        stats = db.get_statistics()
        
        # Получаем статистику по коллекциям
        text_stats = stats  # Статистика текстовой коллекции
        
        # Статистика коллекции изображений
        try:
            image_collection_info = db.client.get_collection(db.image_collection_name)
            image_stats = {
                "points_count": image_collection_info.points_count,
                "vectors_count": image_collection_info.vectors_count
            }
        except Exception:
            image_stats = {"points_count": 0, "vectors_count": 0}
        
        return {
            "text_articles": text_stats.get("articles_count", 0),
            "images": image_stats.get("points_count", 0),
            "total_vectors": text_stats.get("vectors_count", 0) + image_stats.get("vectors_count", 0),
            "indexed_vectors": text_stats.get("indexed_vectors_count", 0)
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}", exc_info=True)
        return {
            "error": str(e),
            "text_articles": 0,
            "images": 0,
            "total_vectors": 0
        }


# ========== RESOURCES ==========

@mcp.resource("kb://statistics")
def kb_statistics_resource() -> List[str]:
    """
    Ресурс: статистика KB в текстовом формате.
    """
    try:
        stats = get_kb_statistics()
        
        if "error" in stats:
            return [f"Ошибка получения статистики: {stats['error']}"]
        
        return [
            f"📊 Статистика базы знаний 3dtoday:",
            f"  • Статей: {stats.get('text_articles', 0)}",
            f"  • Изображений: {stats.get('images', 0)}",
            f"  • Всего векторов: {stats.get('total_vectors', 0)}",
            f"  • Проиндексировано: {stats.get('indexed_vectors', 0)}"
        ]
        
    except Exception as e:
        return [f"Ошибка: {str(e)}"]


# ========== PROMPTS ==========

@mcp.prompt(
    name="diagnostic_prompt",
    description="Промпт для диагностики проблемы 3D-печати на основе запроса пользователя"
)
def diagnostic_prompt(
    user_query: str,
    printer_model: Optional[str] = None,
    material: Optional[str] = None,
    has_image: bool = False
) -> List[Message]:
    """
    Генерирует промпт для диагностики проблемы на основе запроса пользователя.
    
    Args:
        user_query: Запрос пользователя
        printer_model: Модель принтера (опционально)
        material: Материал (опционально)
        has_image: Есть ли изображение дефекта
    """
    prompt_text = f"""Ты - эксперт по диагностике проблем 3D-печати.

ЗАПРОС ПОЛЬЗОВАТЕЛЯ: {user_query}
"""
    
    if printer_model:
        prompt_text += f"\nМОДЕЛЬ ПРИНТЕРА: {printer_model}"
    
    if material:
        prompt_text += f"\nМАТЕРИАЛ: {material}"
    
    if has_image:
        prompt_text += "\n\n⚠️ ПОЛЬЗОВАТЕЛЬ ПРИЛОЖИЛ ФОТО ДЕФЕКТА. Проанализируй изображение и используй его для диагностики."
    
    prompt_text += """

ИСПОЛЬЗУЙ ИНСТРУМЕНТЫ:
1. search_kb_articles() - для поиска релевантных статей в базе знаний
   - Используй фильтры (problem_type, printer_model, material) для точного поиска
2. get_article_by_id() - для получения полной информации о конкретной статье

ЗАДАЧА:
1. Найди релевантные статьи в KB, используя инструменты
2. Проанализируй найденную информацию
3. Дай конкретные рекомендации с параметрами (температура, скорость, retraction и т.д.)
4. Если информации недостаточно - задай уточняющие вопросы пользователю

ОТВЕТ ДОЛЖЕН БЫТЬ:
- Конкретным (с параметрами: температура, скорость, retraction)
- Структурированным (проблема → решение → параметры)
- С ссылками на источники из KB (если есть)
- Понятным для пользователя (без излишнего технического жаргона)
"""
    
    return [Message(role="user", content=TextContent(type="text", text=prompt_text))]


# ========== RUN SERVER ==========

if __name__ == "__main__":
    print("="*60)
    print("🚀 Запуск KB MCP Server для проекта 3dtoday")
    print("="*60)
    print("\n📋 Доступные инструменты:")
    print("  • search_kb_articles() - поиск статей в KB")
    print("  • get_article_by_id() - получение статьи по ID")
    print("  • get_kb_statistics() - статистика KB")
    print("  • parse_document() - парсинг документов (HTML/PDF/JSON) с анализом")
    print("\n📚 Доступные ресурсы:")
    print("  • kb://statistics - статистика KB")
    print("\n💬 Доступные промпты:")
    print("  • diagnostic_prompt - промпт для диагностики")
    print("\n" + "="*60)
    print("✅ Сервер готов к работе (stdio transport)")
    print("="*60 + "\n")
    
    mcp.run(transport="stdio")

