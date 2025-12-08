"""
FastAPI приложение для проекта 3dtoday
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import json
from dotenv import load_dotenv

# Импорт моделей (относительный путь)
try:
    from app.models.schemas import (
        ArticleInput,
        DiagnosticRequest,
        DiagnosticResponse,
        ValidationResponse,
        ClarificationQuestion
    )
except ImportError:
    # Fallback для прямого запуска
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from models.schemas import (
        ArticleInput,
        DiagnosticRequest,
        DiagnosticResponse,
        ValidationResponse,
        ClarificationQuestion
    )

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / "config.env")

# Настройка логирования с записью в файл
try:
    from app.utils.logger_config import get_api_logger
    logger = get_api_logger()
except ImportError:
    # Fallback если logger_config недоступен
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    )
    logger = logging.getLogger(__name__)

# Кастомный JSON encoder для правильной обработки Unicode
class UnicodeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


# Создание FastAPI приложения
app = FastAPI(
    title="3dtoday Diagnostic API",
    description="API для диагностики проблем 3D-печати и управления базой знаний",
    version="0.1.0"
)

# Устанавливаем UnicodeJSONResponse как класс ответа по умолчанию
app.router.default_response_class = UnicodeJSONResponse

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production ограничить
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Модели импортированы из models.schemas


# ========== ИМПОРТЫ СЕРВИСОВ ==========

try:
    import sys
    from pathlib import Path
    # Добавляем путь к модулям
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    from services.article_indexer import get_article_indexer
    from services.rag_service import get_rag_service
    from services.llm_client import get_llm_client
    from tools.article_collector import ArticleCollector
except ImportError as e:
    logger.error(f"Ошибка импорта сервисов: {e}")
    # Fallback для тестирования
    get_article_indexer = None
    get_rag_service = None
    get_llm_client = None
    ArticleCollector = None


# ========== ENDPOINTS ДЛЯ АДМИНИСТРАТОРОВ ==========

@app.post("/api/kb/articles/parse_with_llm", response_class=UnicodeJSONResponse)
async def parse_url_with_llm(
    request: Optional[Dict[str, Any]] = Body(None),
    url: Optional[str] = Body(None),
    llm_provider: Optional[str] = Body(None),
    model: Optional[str] = Body(None)
):
    """
    Парсинг URL напрямую через LLM (GPT-4o или Gemini 3)
    LLM сам загружает контент и формирует JSON для KB
    
    Body: {
        "url": "URL для анализа",
        "llm_provider": "openai|gemini" (опционально),
        "model": "название модели" (опционально)
    }
    
    Преимущества:
    - LLM сам определяет структуру контента
    - Более интеллектуальное извлечение информации
    - Анализ изображений через мультимодальные возможности
    - Автоматическое формирование JSON для KB
    """
    try:
        if request:
            url = url or request.get("url")
            llm_provider = llm_provider or request.get("llm_provider", "openai")
            model = model or request.get("model")
        else:
            url = url
            llm_provider = llm_provider or "openai"
        
        if not url:
            raise HTTPException(status_code=400, detail="url обязателен")
        
        if llm_provider not in ["openai", "gemini"]:
            raise HTTPException(status_code=400, detail="llm_provider должен быть 'openai' или 'gemini'")
        
        from services.llm_url_analyzer import LLMURLAnalyzer
        
        analyzer = LLMURLAnalyzer(llm_provider=llm_provider, model=model)
        result = await analyzer.analyze_url(url)
        
        if not result:
            raise HTTPException(status_code=500, detail="Не удалось проанализировать URL через LLM")
        
        return {
            "success": True,
            "method": "llm_direct",
            "llm_provider": llm_provider,
            "model": analyzer.model,
            "parsed_document": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка парсинга URL через LLM: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kb/articles/parse")
async def parse_document(
    request: Optional[Dict[str, Any]] = Body(None),
    source: Optional[str] = Body(None),
    source_type: Optional[str] = Body(None),
    llm_provider: Optional[str] = Body(None),
    model: Optional[str] = Body(None),
    timeout: Optional[int] = Body(None)
):
    """
    Парсинг документа из разных источников и анализ через агента-библиотекаря
    
    Body: {
        "source": "URL или путь к файлу, или JSON строка",
        "source_type": "auto|html|pdf|json|url" (опционально),
        "llm_provider": "openai|ollama|gemini" (опционально),
        "model": "название модели" (опционально),
        "timeout": 180 (опционально, секунды)
    }
    
    Поддерживает:
    - HTML/URL: статьи с сайтов (например, 3dtoday.ru)
    - PDF: документация оборудования, инструкции
    - JSON: импорт существующих блоков KB в стандартном формате
    
    Типы контента:
    - article: решение проблем 3D-печати
    - documentation: документация оборудования
    - comparison: сравнения материалов/принтеров
    - technical: технические детали и характеристики
    """
    try:
        # Поддержка старого формата (request как dict) и нового (отдельные параметры)
        if request:
            source = source or request.get("source") or request.get("url")
            source_type = source_type or request.get("source_type")
            llm_provider = llm_provider or request.get("llm_provider")
            model = model or request.get("model")
            timeout = timeout or request.get("timeout")
        
        if not source:
            raise HTTPException(status_code=400, detail="source обязателен")
        
        # Временное изменение провайдера и модели если указаны
        original_provider = None
        original_model = None
        
        if llm_provider:
            original_provider = os.getenv("LLM_PROVIDER")
            os.environ["LLM_PROVIDER"] = llm_provider
        
        if model:
            if llm_provider == "openai":
                original_model = os.getenv("OPENAI_MODEL")
                os.environ["OPENAI_MODEL"] = model
            elif llm_provider == "ollama":
                original_model = os.getenv("OLLAMA_MODEL")
                os.environ["OLLAMA_MODEL"] = model
            elif llm_provider == "gemini":
                original_model = os.getenv("GEMINI_MODEL")
                os.environ["GEMINI_MODEL"] = model
        
        if timeout:
            os.environ["MCP_SERVER_TIMEOUT"] = str(timeout)
        
        # Используем универсальный парсер документов
        from services.document_parser import DocumentParser
        from agents.kb_librarian import KBLibrarianAgent
        
        parser = DocumentParser()
        doc_data = await parser.parse_document(source, source_type)
        
        if not doc_data:
            raise HTTPException(status_code=404, detail="Не удалось распарсить документ")
        
        # Полный цикл: анализ + решение о публикации через агента-библиотекаря
        # Передаем провайдер и модель в агента для правильной инициализации
        librarian = KBLibrarianAgent(llm_provider=llm_provider, model=model, timeout=timeout)
        review_result = await librarian.review_and_decide(
            title=doc_data["title"],
            content=doc_data["content"],
            images=doc_data.get("images", []),
            url=doc_data.get("url"),
            content_type=doc_data.get("content_type"),
            is_questions_list=doc_data.get("is_questions_list", False)
        )
        
        # Восстанавливаем оригинальные настройки
        if original_provider:
            os.environ["LLM_PROVIDER"] = original_provider
        if original_model:
            if llm_provider == "openai":
                os.environ["OPENAI_MODEL"] = original_model
            elif llm_provider == "ollama":
                os.environ["OLLAMA_MODEL"] = original_model
            elif llm_provider == "gemini":
                os.environ["GEMINI_MODEL"] = original_model
        
        return {
            "success": True,
            "parsed_document": doc_data,
            "review": review_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка парсинга документа: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kb/articles/validate", response_model=ValidationResponse)
async def validate_article(article: ArticleInput):
    """
    Валидация релевантности статьи перед добавлением в KB
    """
    try:
        if ArticleCollector is None:
            raise HTTPException(status_code=503, detail="ArticleCollector не инициализирован")
        
        collector = ArticleCollector()
        
        validation = await collector.validate_article_relevance(
            title=article.title,
            content=article.content,
            url=article.url
        )
        
        metadata = None
        if validation.get("is_relevant", False):
            metadata = await collector.extract_metadata(article.title, article.content)
        
        return ValidationResponse(
            is_relevant=validation.get("is_relevant", False),
            relevance_score=validation.get("relevance_score", 0.0),
            quality_score=validation.get("quality_score", 0.0),
            has_solutions=validation.get("has_solutions", False),
            issues=validation.get("issues", []),
            recommendations=validation.get("recommendations", []),
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Ошибка валидации статьи: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kb/articles/add_from_parse", response_class=UnicodeJSONResponse)
async def add_article_from_parse(request: Dict[str, Any] = Body(...)):
    """
    Добавление статьи в KB из результата парсинга с учетом решения администратора
    """
    try:
        if get_article_indexer is None:
            raise HTTPException(status_code=503, detail="ArticleIndexer не инициализирован")
        
        parsed_document = request.get("parsed_document", {})
        review = request.get("review", {})
        admin_decision = request.get("admin_decision", "needs_review")
        relevance_threshold = request.get("relevance_threshold", 0.6)
        
        # Проверка решения администратора
        if admin_decision != "approve":
            raise HTTPException(
                status_code=400,
                detail=f"Статья не может быть добавлена: решение администратора - {admin_decision}"
            )
        
        # Проверка релевантности относительно порога
        relevance_score = review.get("relevance_score", 0.0)
        if relevance_score < relevance_threshold:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Релевантность ({relevance_score:.2f}) ниже установленного порога "
                    f"({relevance_threshold:.2f}). Статья не может быть добавлена автоматически."
                )
            )
        
        indexer = get_article_indexer()
        
        # Подготовка данных статьи из распарсенного документа
        title = parsed_document.get("title", "")
        content = parsed_document.get("content", "")
        url = parsed_document.get("url", "")
        section = parsed_document.get("section", "unknown")
        
        # Генерация article_id
        article_id = f"{section}_{abs(hash(title)) % 10000}"
        
        # Извлечение метаданных из review
        summary = review.get("summary", {})
        content_type = summary.get("content_type", "article") if summary else parsed_document.get("content_type", "article")
        
        article_data = {
            "article_id": article_id,
            "title": title,
            "content": content,
            "url": url,
            "section": section,
            "date": parsed_document.get("date", ""),
            "relevance_score": relevance_score,
            "quality_score": review.get("quality_score", 0.0),
            "content_type": content_type,
            "problem": summary.get("problem", "") if summary else "",
            "symptoms": summary.get("symptoms", []) if summary else [],
            "solutions": summary.get("solutions", []) if summary else [],
            "printer_models": summary.get("printer_models", []) if summary else [],
            "materials": summary.get("materials", []) if summary else [],
            "abstract": review.get("abstract", ""),
            "admin_decision": admin_decision,
            "librarian_decision": review.get("decision", "needs_review"),
            "relevance_threshold_used": relevance_threshold
        }
        
        # Индексация статьи
        result = await indexer.index_article(article_data)
        
        if result["success"]:
            # Индексация изображений, если есть
            images = parsed_document.get("images", [])
            if images:
                for img_url in images[:5]:  # Ограничиваем количество изображений
                    try:
                        await indexer.index_image(
                            image_url=img_url,
                            article_id=article_id,
                            title=title
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось добавить изображение {img_url}: {e}")
            
            return {
                "success": True,
                "article_id": article_id,
                "message": "Статья успешно добавлена в KB",
                "relevance_score": relevance_score,
                "relevance_threshold": relevance_threshold,
                "admin_decision": admin_decision
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Ошибка индексации"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка добавления статьи из парсинга: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kb/articles/add_from_parse", response_class=UnicodeJSONResponse)
async def add_article_from_parse(request: Dict[str, Any] = Body(...)):
    """
    Добавление статьи в KB из результата парсинга с учетом решения администратора
    """
    try:
        if get_article_indexer is None:
            raise HTTPException(status_code=503, detail="ArticleIndexer не инициализирован")
        
        parsed_document = request.get("parsed_document", {})
        review = request.get("review", {})
        admin_decision = request.get("admin_decision", "needs_review")
        relevance_threshold = request.get("relevance_threshold", 0.6)
        
        # Проверка решения администратора
        if admin_decision != "approve":
            raise HTTPException(
                status_code=400,
                detail=f"Статья не может быть добавлена: решение администратора - {admin_decision}"
            )
        
        # Проверка релевантности относительно порога
        relevance_score = review.get("relevance_score", 0.0)
        if relevance_score < relevance_threshold:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Релевантность ({relevance_score:.2f}) ниже установленного порога "
                    f"({relevance_threshold:.2f}). Статья не может быть добавлена автоматически."
                )
            )
        
        indexer = get_article_indexer()
        
        # Подготовка данных статьи из распарсенного документа
        title = parsed_document.get("title", "")
        content = parsed_document.get("content", "")
        url = parsed_document.get("url", "")
        section = parsed_document.get("section", "unknown")
        
        # Генерация article_id
        article_id = f"{section}_{abs(hash(title)) % 10000}"
        
        # Извлечение метаданных из review
        summary = review.get("summary", {})
        content_type = summary.get("content_type", "article") if summary else parsed_document.get("content_type", "article")
        
        article_data = {
            "article_id": article_id,
            "title": title,
            "content": content,
            "url": url,
            "section": section,
            "date": parsed_document.get("date", ""),
            "relevance_score": relevance_score,
            "quality_score": review.get("quality_score", 0.0),
            "content_type": content_type,
            "problem": summary.get("problem", "") if summary else "",
            "symptoms": summary.get("symptoms", []) if summary else [],
            "solutions": summary.get("solutions", []) if summary else [],
            "printer_models": summary.get("printer_models", []) if summary else [],
            "materials": summary.get("materials", []) if summary else [],
            "abstract": review.get("abstract", ""),
            "admin_decision": admin_decision,
            "librarian_decision": review.get("decision", "needs_review"),
            "relevance_threshold_used": relevance_threshold
        }
        
        # Индексация статьи
        result = await indexer.index_article(article_data)
        
        if result["success"]:
            # Индексация изображений, если есть
            images = parsed_document.get("images", [])
            if images:
                for img_url in images[:5]:  # Ограничиваем количество изображений
                    try:
                        if isinstance(img_url, dict):
                            img_url_str = img_url.get("url", "")
                        else:
                            img_url_str = str(img_url)
                        if img_url_str:
                            await indexer.index_image(
                                image_url=img_url_str,
                                article_id=article_id,
                                title=title
                            )
                    except Exception as e:
                        logger.warning(f"Не удалось добавить изображение {img_url}: {e}")
            
            return {
                "success": True,
                "article_id": article_id,
                "message": "Статья успешно добавлена в KB",
                "relevance_score": relevance_score,
                "relevance_threshold": relevance_threshold,
                "admin_decision": admin_decision
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Ошибка индексации"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка добавления статьи из парсинга: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kb/articles/add")
async def add_article(article: ArticleInput):
    """
    Добавление статьи в KB после валидации (старый метод для ручного ввода)
    """
    try:
        if get_article_indexer is None:
            raise HTTPException(status_code=503, detail="ArticleIndexer не инициализирован")
        
        indexer = get_article_indexer()
        collector = ArticleCollector()
        
        # Валидация
        validation = await collector.validate_article_relevance(
            title=article.title,
            content=article.content,
            url=article.url
        )
        
        if not validation.get("is_relevant", False):
            raise HTTPException(
                status_code=400,
                detail=f"Статья не релевантна (relevance_score: {validation.get('relevance_score', 0):.2f})"
            )
        
        # Извлечение метаданных
        metadata = await collector.extract_metadata(article.title, article.content)
        
        if not metadata.get("problem_type"):
            raise HTTPException(
                status_code=400,
                detail="Не удалось определить тип проблемы"
            )
        
        # Подготовка статьи
        article_id = f"{metadata['problem_type']}_{abs(hash(article.title)) % 10000}"
        
        article_data = {
            "article_id": article_id,
            "title": article.title,
            "content": article.content,
            "url": article.url or "",
            "section": article.section or "unknown",
            "date": "",
            "relevance_score": validation.get("relevance_score", 0.0),
            "problem_type": metadata.get("problem_type"),
            "printer_models": metadata.get("printer_models", []),
            "materials": metadata.get("materials", []),
            "symptoms": metadata.get("symptoms", []),
            "solutions": metadata.get("solutions", [])
        }
        
        # Индексация
        result = await indexer.index_article(article_data)
        
        if result["success"]:
            return {
                "success": True,
                "article_id": article_id,
                "message": "Статья успешно добавлена в KB",
                "metadata": metadata,
                "validation": validation
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Ошибка индексации")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка добавления статьи: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kb/statistics", response_class=UnicodeJSONResponse)
async def get_kb_statistics():
    """
    Получение статистики KB
    
    Returns:
        {
            "text_articles": количество текстовых статей,
            "images": количество изображений,
            "total_vectors": общее количество векторов
        }
    """
    try:
        from services.vector_db import get_vector_db
        
        db = get_vector_db()
        stats = db.get_statistics()
        
        # Статистика коллекции изображений
        try:
            image_collection_info = db.client.get_collection(db.image_collection_name)
            image_count = image_collection_info.points_count
        except Exception:
            image_count = 0
        
        text_count = stats.get("articles_count", 0)
        text_vectors = stats.get("vectors_count", 0)
        
        return {
            "text_articles": text_count,
            "images": image_count,
            "total_vectors": text_vectors + image_count
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kb/articles/{article_id}", response_class=UnicodeJSONResponse)
async def get_article_by_id(article_id: str):
    """
    Получение статьи по ID
    
    Args:
        article_id: ID статьи (может быть article_id или original_id)
    
    Returns:
        Полная информация о статье или ошибка, если статья не найдена
    """
    try:
        from services.vector_db import get_vector_db
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        db = get_vector_db()
        
        # Поиск статьи по ID через scroll
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
            # Пробуем найти по original_id
            filter_conditions_orig = [
                FieldCondition(
                    key="original_id",
                    match=MatchValue(value=article_id)
                )
            ]
            
            qdrant_filter_orig = Filter(must=filter_conditions_orig)
            result_orig = db.client.scroll(
                collection_name=db.collection_name,
                scroll_filter=qdrant_filter_orig,
                limit=1,
                with_payload=True,
                with_vectors=False
            )
            
            if result_orig[0] and len(result_orig[0]) > 0:
                point = result_orig[0][0]
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
            
            raise HTTPException(status_code=404, detail=f"Статья с ID '{article_id}' не найдена в KB")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения статьи: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kb/articles", response_class=UnicodeJSONResponse)
async def list_articles(limit: int = 10, offset: int = 0):
    """
    Список статей в KB
    
    Args:
        limit: Количество статей (по умолчанию 10)
        offset: Смещение (по умолчанию 0)
    
    Returns:
        Список статей с краткой информацией
    """
    try:
        from services.vector_db import get_vector_db
        
        db = get_vector_db()
        
        # Получаем статьи через scroll
        result = db.client.scroll(
            collection_name=db.collection_name,
            limit=limit + offset,
            with_payload=True,
            with_vectors=False
        )
        
        points = result[0]
        
        # Применяем offset
        articles = []
        for point in points[offset:offset+limit]:
            payload = point.payload
            articles.append({
                "article_id": payload.get("article_id") or payload.get("original_id", f"point_{point.id}"),
                "title": payload.get("title", "Без названия"),
                "url": payload.get("url"),
                "section": payload.get("section"),
                "problem_type": payload.get("problem_type"),
                "content_preview": payload.get("content", "")[:200] + "..." if len(payload.get("content", "")) > 200 else payload.get("content", "")
            })
        
        return {
            "articles": articles,
            "total": len(points),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения списка статей: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== ENDPOINTS ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ==========

@app.post("/api/diagnose", response_model=DiagnosticResponse)
async def diagnose_problem(request: DiagnosticRequest):
    """
    Диагностика проблемы 3D-печати
    """
    try:
        if get_rag_service is None or get_llm_client is None:
            raise HTTPException(status_code=503, detail="Сервисы не инициализированы")
        
        rag_service = get_rag_service()
        llm_client = get_llm_client()
        
        # Построение фильтров из запроса
        filters = {}
        if request.problem_type:
            filters["problem_type"] = request.problem_type
        if request.printer_model:
            filters["printer_models"] = [request.printer_model]
        if request.material:
            filters["materials"] = [request.material]
        
        # Поиск в KB
        search_results = await rag_service.hybrid_search(
            query=request.query,
            filters=filters if filters else None,
            limit=3,
            boost_filters=True
        )
        
        # Определение необходимости уточнений
        needs_clarification = False
        clarification_questions = []
        
        # Проверка наличия необходимой информации
        if not request.printer_model:
            needs_clarification = True
            clarification_questions.append(
                ClarificationQuestion(
                    question="Какая у вас модель принтера?",
                    question_type="printer_model",
                    options=None  # Можно добавить список популярных моделей
                )
            )
        
        if not request.material:
            needs_clarification = True
            clarification_questions.append(
                ClarificationQuestion(
                    question="Какой материал вы используете? (PLA, PETG, ABS, etc.)",
                    question_type="material",
                    options=["PLA", "PETG", "ABS", "TPU", "Другое"]
                )
            )
        
        # Если есть результаты поиска, но их мало или низкая релевантность
        if search_results and len(search_results) < 2:
            if search_results[0].get("score", 0) < 0.7:
                needs_clarification = True
                clarification_questions.append(
                    ClarificationQuestion(
                        question="Можете описать проблему подробнее? Что именно происходит?",
                        question_type="symptom",
                        options=None
                    )
                )
        
        # Формирование ответа через LLM
        context = ""
        if search_results:
            context = "\n\n".join([
                f"Статья: {r.get('title', '')}\n{r.get('content', '')[:500]}..."
                for r in search_results[:3]
            ])
        
        prompt = f"""Ты эксперт по диагностике проблем 3D-печати.

ЗАПРОС ПОЛЬЗОВАТЕЛЯ: {request.query}
"""
        
        if request.printer_model:
            prompt += f"\nМОДЕЛЬ ПРИНТЕРА: {request.printer_model}"
        
        if request.material:
            prompt += f"\nМАТЕРИАЛ: {request.material}"
        
        if context:
            prompt += f"\n\nРЕЛЕВАНТНЫЕ СТАТЬИ ИЗ БАЗЫ ЗНАНИЙ:\n{context}"
        
        prompt += """

ЗАДАЧА:
1. Проанализируй запрос пользователя
2. Используй информацию из релевантных статей
3. Дай конкретные рекомендации с параметрами (температура, скорость, retraction)
4. Если информации недостаточно - укажи, что нужны уточнения

ОТВЕТ ДОЛЖЕН БЫТЬ:
- Конкретным (с параметрами)
- Структурированным (проблема → решение → параметры)
- Понятным для пользователя
- Ссылками на источники (если есть)
"""
        
        answer = await llm_client.generate(
            prompt=prompt,
            system_prompt="Ты эксперт по диагностике проблем 3D-печати. Отвечай конкретно и структурированно."
        )
        
        # Оценка уверенности
        confidence = 0.8 if search_results and search_results[0].get("score", 0) > 0.7 else 0.5
        
        return DiagnosticResponse(
            answer=answer,
            needs_clarification=needs_clarification,
            clarification_questions=clarification_questions if needs_clarification else None,
            relevant_articles=[
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "score": r.get("score", 0.0)
                }
                for r in search_results[:3]
            ] if search_results else None,
            confidence=confidence
        )
        
    except HTTPException:
        raise
    except ConnectionError as e:
        error_msg = str(e)
        if "ollama" in error_msg.lower() or "connection refused" in error_msg.lower():
            logger.error(f"Ошибка подключения к LLM сервису: {e}", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail=(
                    "LLM сервис недоступен. "
                    "Убедитесь, что Ollama запущен (ollama serve) или настройте другой провайдер (Gemini/OpenAI) в config.env"
                )
            )
        else:
            logger.error(f"Ошибка подключения: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail=f"Ошибка подключения к сервису: {error_msg}")
    except Exception as e:
        logger.error(f"Ошибка диагностики: {e}", exc_info=True)
        error_msg = str(e)
        # Проверяем, не связана ли ошибка с недоступностью LLM
        if "connection refused" in error_msg.lower() or "errno 111" in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail=(
                    "LLM сервис недоступен. "
                    "Проверьте настройки LLM_PROVIDER в config.env и убедитесь, что выбранный провайдер запущен и доступен."
                )
            )
        raise HTTPException(status_code=500, detail=f"Ошибка диагностики: {error_msg}")


@app.post("/api/diagnose/image")
async def diagnose_with_image(
    query: str,
    printer_model: Optional[str] = None,
    material: Optional[str] = None,
    image: UploadFile = File(...)
):
    """
    Диагностика с анализом изображения дефекта
    """
    try:
        # TODO: Реализовать анализ изображения через Vision Agent
        # Пока возвращаем базовую диагностику
        
        return {
            "message": "Анализ изображений будет реализован в ШАГЕ 8",
            "query": query,
            "printer_model": printer_model,
            "material": material
        }
        
    except Exception as e:
        logger.error(f"Ошибка диагностики с изображением: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== СЛУЖЕБНЫЕ ENDPOINTS ==========

@app.get("/health")
async def health_check():
    """Проверка здоровья API"""
    return {
        "status": "healthy",
        "version": "0.1.0"
    }


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "message": "3dtoday Diagnostic API",
        "version": "0.1.0",
        "endpoints": {
            "diagnose": "/api/diagnose",
            "kb_validate": "/api/kb/articles/validate",
            "kb_add": "/api/kb/articles/add",
            "kb_statistics": "/api/kb/statistics",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    uvicorn.run(app, host=host, port=port, reload=True)

