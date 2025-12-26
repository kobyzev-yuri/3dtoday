"""
FastAPI приложение для проекта 3dtoday
"""

import os
import logging
import base64
import httpx as httpx_client
import tempfile
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
        ArticleUpdate,
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
        ArticleUpdate,
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
    model: Optional[str] = Body(None),
    llm_timeout: Optional[int] = Body(None)
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
            llm_timeout = llm_timeout or request.get("llm_timeout")
        else:
            url = url
            llm_provider = llm_provider or "openai"
        
        if not url:
            raise HTTPException(status_code=400, detail="url обязателен")
        
        if llm_provider not in ["openai", "gemini"]:
            raise HTTPException(status_code=400, detail="llm_provider должен быть 'openai' или 'gemini'")
        
        from services.llm_url_analyzer import LLMURLAnalyzer
        
        analyzer = LLMURLAnalyzer(llm_provider=llm_provider, model=model, timeout=llm_timeout)
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
    timeout: Optional[int] = Body(None),
    llm_timeout: Optional[int] = Body(None),
    max_pages: Optional[int] = Body(None)
):
    """
    Парсинг документа из разных источников и анализ через агента-библиотекаря
    
    Body: {
        "source": "URL или путь к файлу, или JSON строка",
        "source_type": "auto|html|pdf|json|url" (опционально),
        "llm_provider": "openai|ollama|gemini" (опционально),
        "model": "название модели" (опционально),
        "timeout": 180 (опционально, секунды),
        "max_pages": 30 (опционально, максимальное количество страниц для PDF, по умолчанию 30 для Gemini)
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
            llm_timeout = llm_timeout or request.get("llm_timeout")
            max_pages = max_pages or request.get("max_pages")
        
        if not source:
            raise HTTPException(status_code=400, detail="source обязателен")
        
        # Определяем source_type если не указан
        if not source_type:
            if source.lower().endswith('.pdf'):
                source_type = "pdf"
            elif source.startswith('http://') or source.startswith('https://'):
                source_type = "url"
            else:
                source_type = "json"  # По умолчанию
        
        # Для PDF по умолчанию используем Gemini (лучше работает с изображениями)
        if not llm_provider and source_type == "pdf":
            llm_provider = "gemini"
            logger.info(f"📄 Для PDF используется Gemini по умолчанию (лучше для анализа изображений)")
        
        # Для Gemini по умолчанию ограничиваем PDF до 30 страниц
        if max_pages is None and llm_provider == "gemini" and source_type == "pdf":
            max_pages = 30
            logger.info(f"📄 Ограничение PDF до {max_pages} страниц для Gemini")
        
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
        
        logger.info(f"📥 Начало парсинга документа: source_type={source_type}, llm_provider={llm_provider}, max_pages={max_pages}")
        
        parser = DocumentParser()
        doc_data = await parser.parse_document(source, source_type, max_pages=max_pages)
        
        if not doc_data:
            logger.error(f"❌ Не удалось распарсить документ: {source[:100]}")
            raise HTTPException(status_code=404, detail="Не удалось распарсить документ")
        
        logger.info(f"✅ Документ распарсен: title={doc_data.get('title', 'N/A')[:50]}, content_length={len(doc_data.get('content', ''))}, images_count={len(doc_data.get('images', []))}")
        
        # Фильтрация изображений по релевантности для мультимодальной KB
        images = doc_data.get("images", [])
        if images:
            logger.info(f"📷 Найдено {len(images)} изображений в документе")
            # Агент-библиотекарь проверит релевантность изображений при анализе
            # Пока передаем все изображения, фильтрация будет выполнена в review_and_decide
        
        # Полный цикл: анализ + решение о публикации через агента-библиотекаря
        # Передаем провайдер и модель в агента для правильной инициализации
        # Используем llm_timeout если указан, иначе timeout (для обратной совместимости)
        final_llm_timeout = llm_timeout or timeout
        logger.info(f"🤖 Инициализация агента-библиотекаря: llm_provider={llm_provider}, model={model}, timeout={final_llm_timeout}")
        
        try:
            librarian = KBLibrarianAgent(llm_provider=llm_provider, model=model, timeout=final_llm_timeout)
            logger.info(f"📋 Начало анализа через агента-библиотекаря...")
            review_result = await librarian.review_and_decide(
                title=doc_data["title"],
                content=doc_data["content"],
                images=images,  # Передаем изображения для анализа релевантности
                url=doc_data.get("url"),
                content_type=doc_data.get("content_type"),
                is_questions_list=doc_data.get("is_questions_list", False)
            )
            logger.info(f"✅ Анализ завершен: relevance_score={review_result.get('relevance_score', 'N/A')}")
            
            # Если документ релевантен, помечаем изображения как релевантные
            if review_result.get("is_relevant", False) and images:
                logger.info(f"✅ Документ релевантен, изображения будут проиндексированы в мультимодальную KB")
        except Exception as e:
            logger.error(f"❌ Ошибка при анализе через агента-библиотекаря: {e}", exc_info=True)
            raise
        
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
                # Изображения индексируются в другом месте (в более полной версии endpoint)
                # Здесь просто логируем, что они есть
                logger.info(f"📷 Найдено {len(images)} изображений в статье. Индексация изображений выполняется в расширенной версии endpoint.")
            
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
            indexed_images = []
            if images:
                from app.services.vision_analyzer import VisionAnalyzer
                from app.agents.kb_librarian import KBLibrarianAgent
                
                # Используем VisionAnalyzer для анализа изображений
                vision_analyzer = VisionAnalyzer(prefer_ollama=False)
                availability = vision_analyzer.check_availability()
                
                if availability.get('available', False):
                    logger.info(f"📷 Анализ изображений через {availability.get('provider', 'unknown')}")
                    
                    # Обрабатываем до 20 изображений (увеличили лимит)
                    for img_idx, img_data in enumerate(images[:20]):
                        try:
                            if isinstance(img_data, dict):
                                img_url = img_data.get("url", "")
                                img_title = img_data.get("title", img_data.get("alt", f"Image {img_idx + 1}"))
                                img_base64 = img_data.get("data")  # Base64 данные, если есть
                            else:
                                img_url = str(img_data)
                                img_title = f"Image {img_idx + 1}"
                                img_base64 = None
                            
                            if not img_url and not img_base64:
                                continue
                            
                            # Анализ изображения через Vision API
                            try:
                                if img_base64:
                                    # Если есть base64 данные (из PDF)
                                    analysis_result = vision_analyzer.analyze_image_from_base64(img_base64, img_title)
                                elif img_url.startswith('http'):
                                    # Если это URL - скачиваем и анализируем
                                    analysis_result = vision_analyzer.analyze_image_from_url(img_url, img_title)
                                else:
                                    # Локальный файл
                                    analysis_result = vision_analyzer.analyze_image_from_path(Path(img_url))
                                
                                # Проверяем успешность анализа и релевантность
                                if analysis_result and analysis_result.get("success", False):
                                    # Получаем текст анализа
                                    analysis_text = analysis_result.get("analysis", "")
                                    
                                    # Проверяем релевантность изображения к 3D-печати
                                    relevance_check = vision_analyzer.check_relevance_to_3d_printing(analysis_text, img_title)
                                    
                                    if not relevance_check.get("success", False) or not relevance_check.get("is_relevant", True):
                                        logger.info(f"⚠️ Изображение {img_idx + 1} не релевантно 3D-печати, пропускаем")
                                        continue
                                    
                                    # Создаем метаданные для индексации
                                    image_metadata = {
                                        "article_id": f"{article_id}_img_{img_idx + 1}",
                                        "title": img_title,
                                        "content": analysis_text,  # Используем полный анализ как content
                                        "abstract": analysis_text[:500] if len(analysis_text) > 500 else analysis_text,  # Краткий абстракт
                                        "problem_type": relevance_check.get("problem_type") or (summary.get("problem_type") if summary else None),
                                        "printer_models": relevance_check.get("printer_models", []) or (summary.get("printer_models", []) if summary else []),
                                        "materials": relevance_check.get("materials", []) or (summary.get("materials", []) if summary else []),
                                        "symptoms": summary.get("symptoms", []) if summary else []
                                    }
                                    
                                    # Скачиваем изображение во временный файл для индексации
                                    import tempfile
                                    import httpx as httpx_client
                                    
                                    temp_dir = Path(tempfile.gettempdir()) / "kb_images"
                                    temp_dir.mkdir(exist_ok=True)
                                    
                                    if img_base64:
                                        # Сохраняем base64 изображение
                                        image_bytes = base64.b64decode(img_base64)
                                        temp_path = temp_dir / f"{article_id}_img_{img_idx + 1}.jpg"
                                        with open(temp_path, 'wb') as f:
                                            f.write(image_bytes)
                                    elif img_url.startswith('http'):
                                        # Скачиваем изображение по URL
                                        async with httpx_client.AsyncClient(timeout=30) as client:
                                            img_response = await client.get(img_url)
                                            img_response.raise_for_status()
                                            temp_path = temp_dir / f"{article_id}_img_{img_idx + 1}.jpg"
                                            with open(temp_path, 'wb') as f:
                                                f.write(img_response.content)
                                    else:
                                        temp_path = Path(img_url)
                                    
                                    # Индексация изображения
                                    index_result = await indexer.index_image(
                                        image_data=image_metadata,
                                        image_path=str(temp_path),
                                        generate_embedding=True
                                    )
                                    
                                    if index_result.get("success"):
                                        indexed_images.append({
                                            "image_id": image_metadata["article_id"],
                                            "abstract": image_metadata.get("abstract", "")
                                        })
                                        logger.info(f"✅ Изображение {img_idx + 1} проанализировано и проиндексировано")
                                    
                            except Exception as img_error:
                                logger.warning(f"⚠️ Ошибка анализа изображения {img_idx + 1}: {img_error}")
                                
                        except Exception as e:
                            logger.warning(f"⚠️ Не удалось обработать изображение {img_idx + 1}: {e}")
                else:
                    logger.warning(f"⚠️ Vision API недоступен ({availability.get('message', 'unknown')}), изображения не будут проанализированы")
            
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


@app.delete("/api/kb/articles/{article_id}", response_class=UnicodeJSONResponse)
async def delete_article(article_id: str):
    """
    Удаление статьи по ID
    
    Args:
        article_id: ID статьи
    
    Returns:
        Результат удаления
    """
    try:
        from services.vector_db import get_vector_db
        
        db = get_vector_db()
        
        success = await db.delete_article(article_id)
        
        if success:
            return {
                "success": True,
                "message": f"Статья {article_id} успешно удалена",
                "article_id": article_id
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Статья с ID {article_id} не найдена"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления статьи: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/kb/articles/{article_id}", response_class=UnicodeJSONResponse)
async def update_article(article_id: str, article_update: ArticleUpdate):
    """
    Обновление статьи по ID
    
    Args:
        article_id: ID статьи
        article_update: Данные для обновления
    
    Returns:
        Обновленная статья
    """
    try:
        from services.vector_db import get_vector_db
        
        db = get_vector_db()
        
        # Подготовка данных для обновления (только не-None поля)
        update_data = {}
        if article_update.title is not None:
            update_data["title"] = article_update.title
        if article_update.content is not None:
            update_data["content"] = article_update.content
        if article_update.url is not None:
            update_data["url"] = article_update.url
        if article_update.section is not None:
            update_data["section"] = article_update.section
        if article_update.problem_type is not None:
            update_data["problem_type"] = article_update.problem_type
        if article_update.printer_models is not None:
            update_data["printer_models"] = article_update.printer_models
        if article_update.materials is not None:
            update_data["materials"] = article_update.materials
        if article_update.symptoms is not None:
            update_data["symptoms"] = article_update.symptoms
        if article_update.solutions is not None:
            update_data["solutions"] = article_update.solutions
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="Не указаны поля для обновления"
            )
        
        success = await db.update_article(
            article_id=article_id,
            article_data=update_data,
            regenerate_embedding=article_update.regenerate_embedding
        )
        
        if success:
            # Получаем обновленную статью
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            filter_conditions = [
                FieldCondition(
                    key="article_id",
                    match=MatchValue(value=article_id)
                )
            ]
            
            qdrant_filter = Filter(must=filter_conditions)
            
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
                    "success": True,
                    "message": f"Статья {article_id} успешно обновлена",
                    "article": {
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
                }
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Статья с ID {article_id} не найдена после обновления"
                )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Статья с ID {article_id} не найдена"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления статьи: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kb/metadata/unique-values", response_class=UnicodeJSONResponse)
async def get_unique_metadata_values():
    """
    Получение уникальных значений материалов и принтеров из KB
    
    Returns:
        {
            "materials": ["PLA", "PETG", "ABS", ...],
            "printer_models": ["Ender-3", "Anycubic Kobra", ...]
        }
    """
    try:
        from services.vector_db import get_vector_db
        
        db = get_vector_db()
        
        # Получаем все точки через scroll (с большим лимитом)
        materials_set = set()
        printer_models_set = set()
        
        # Используем scroll для получения всех точек
        limit = 10000  # Большой лимит для получения всех статей
        offset = 0
        
        while True:
            result = db.client.scroll(
                collection_name=db.collection_name,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            points = result[0]
            if not points:
                break
            
            # Собираем уникальные значения
            for point in points:
                payload = point.payload or {}
                
                # Материалы
                materials = payload.get("materials", [])
                if isinstance(materials, list):
                    for material in materials:
                        if material and isinstance(material, str):
                            materials_set.add(material.strip())
                
                # Модели принтеров
                printer_models = payload.get("printer_models", [])
                if isinstance(printer_models, list):
                    for printer_model in printer_models:
                        if printer_model and isinstance(printer_model, str):
                            printer_models_set.add(printer_model.strip())
            
            # Если получили меньше, чем лимит, значит это последняя страница
            if len(points) < limit:
                break
            
            offset += limit
        
        # Сортируем для удобства
        materials_list = sorted(list(materials_set), key=str.lower)
        printer_models_list = sorted(list(printer_models_set), key=str.lower)
        
        logger.info(f"✅ Найдено уникальных материалов: {len(materials_list)}, принтеров: {len(printer_models_list)}")
        
        return {
            "materials": materials_list,
            "printer_models": printer_models_list
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения уникальных значений метаданных: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kb/examples/relevant", response_class=UnicodeJSONResponse)
async def get_relevant_examples(
    candidate_queries: Optional[str] = None,
    limit: int = 8,
    min_score: float = 0.3
):
    """
    Получение релевантных примеров запросов из KB
    
    Args:
        candidate_queries: Список кандидатов через запятую (опционально, для проверки)
        limit: Максимальное количество примеров (по умолчанию 8)
        min_score: Минимальный score релевантности (по умолчанию 0.3)
    
    Returns:
        {
            "examples": [
                {
                    "query": "У меня появляются ниточки...",
                    "score": 0.85,
                    "has_relevant_articles": true
                }
            ]
        }
    """
    try:
        from services.rag_service import get_rag_service
        
        rag_service = get_rag_service()
        relevant_examples = []
        
        # Если переданы кандидаты, проверяем их релевантность
        if candidate_queries:
            candidates = [q.strip() for q in candidate_queries.split(",") if q.strip()]
            logger.info(f"Checking {len(candidates)} candidate queries for relevance")
            
            for query in candidates:
                try:
                    # Быстрый поиск в KB для проверки релевантности
                    results = await rag_service.hybrid_search(
                        query=query,
                        limit=1,  # Достаточно одного результата для проверки
                        boost_filters=False
                    )
                    
                    if results and len(results) > 0:
                        score = results[0].get("score", 0.0)
                        if score >= min_score:
                            relevant_examples.append({
                                "query": query,
                                "score": round(score, 2),
                                "has_relevant_articles": True
                            })
                            logger.debug(f"Query '{query[:50]}...' is relevant (score: {score:.2f})")
                        else:
                            logger.debug(f"Query '{query[:50]}...' has low relevance (score: {score:.2f})")
                    else:
                        logger.debug(f"Query '{query[:50]}...' has no results in KB")
                except Exception as e:
                    logger.warning(f"Error checking query '{query[:50]}...': {e}")
                    continue
        
        # Если кандидаты не переданы или их недостаточно, генерируем примеры из KB
        if len(relevant_examples) < limit:
            logger.info("Generating examples from KB articles")
            
            # Получаем статьи из KB
            from services.vector_db import get_vector_db
            db = get_vector_db()
            
            # Получаем разнообразные статьи
            result = db.client.scroll(
                collection_name=db.collection_name,
                limit=min(limit * 3, 100),  # Берем больше, чтобы выбрать разнообразные
                with_payload=True,
                with_vectors=False
            )
            
            points = result[0]
            seen_queries = {ex["query"] for ex in relevant_examples}
            
            # Генерируем примеры из заголовков и метаданных статей
            for point in points:
                if len(relevant_examples) >= limit:
                    break
                
                payload = point.payload or {}
                title = payload.get("title", "")
                problem_type = payload.get("problem_type", "")
                materials = payload.get("materials", [])
                printer_models = payload.get("printer_models", [])
                
                # Создаем примеры на основе статьи
                examples_from_article = []
                
                # Пример 1: На основе заголовка (естественный запрос)
                if title:
                    # Преобразуем заголовок в естественный запрос пользователя
                    title_lower = title.lower()
                    
                    # Если заголовок уже похож на вопрос, используем его как есть
                    if any(word in title_lower for word in ["как", "почему", "что", "ищу", "помогите", "проблема"]):
                        query = title
                    # Если заголовок описывает проблему, преобразуем в запрос
                    elif problem_type:
                        # Используем более естественные формулировки
                        problem_names = {
                            "stringing": "ниточки между деталями",
                            "warping": "отслоение от стола",
                            "layer_separation": "трещины в слоях",
                            "bed_adhesion": "плохое прилипание к столу",
                            "overhang": "проблемы с нависающими частями",
                            "underextrusion": "недозаполнение",
                            "overextrusion": "перезаполнение"
                        }
                        problem_name = problem_names.get(problem_type, problem_type)
                        
                        if materials and printer_models:
                            query = f"У меня появляются {problem_name} при печати {materials[0]} на {printer_models[0]}"
                        elif materials:
                            query = f"У меня появляются {problem_name} при печати {materials[0]}"
                        else:
                            query = f"Проблема с {problem_name}"
                    else:
                        # Общий запрос на основе заголовка
                        query = f"Ищу информацию о {title.lower()}"
                    
                    if query not in seen_queries and len(query) > 10:
                        examples_from_article.append(query)
                
                # Пример 2: На основе метаданных (конкретный запрос)
                if materials and printer_models and problem_type:
                    material = materials[0]
                    printer = printer_models[0]
                    
                    problem_names = {
                        "stringing": "ниточки между деталями",
                        "warping": "отслаивается от стола",
                        "layer_separation": "трещины в слоях",
                        "bed_adhesion": "не прилипает к столу",
                        "overhang": "плохое качество нависающих частей",
                        "underextrusion": "недозаполнение",
                        "overextrusion": "перезаполнение"
                    }
                    problem_name = problem_names.get(problem_type, problem_type)
                    
                    query = f"Печать {problem_name} при печати {material} на {printer}"
                    
                    if query not in seen_queries:
                        examples_from_article.append(query)
                
                # Пример 3: Простой запрос о проблеме
                if problem_type and problem_type not in [ex.get("query", "") for ex in relevant_examples]:
                    problem_names = {
                        "stringing": "stringing",
                        "warping": "warping",
                        "layer_separation": "трещины в слоях",
                        "bed_adhesion": "прилипание к столу",
                        "overhang": "нависающие части",
                        "underextrusion": "недозаполнение",
                        "overextrusion": "перезаполнение"
                    }
                    problem_name = problem_names.get(problem_type, problem_type)
                    query = f"Как настроить параметры для решения проблемы {problem_name}?"
                    
                    if query not in seen_queries:
                        examples_from_article.append(query)
                
                # Добавляем примеры (быстрая проверка релевантности)
                for query in examples_from_article:
                    if len(relevant_examples) >= limit:
                        break
                    
                    # Быстрая проверка релевантности для сгенерированных примеров
                    try:
                        results = await rag_service.hybrid_search(
                            query=query,
                            limit=1,
                            boost_filters=False
                        )
                        
                        if results and len(results) > 0:
                            score = results[0].get("score", 0.0)
                            if score >= min_score:
                                seen_queries.add(query)
                                relevant_examples.append({
                                    "query": query,
                                    "score": round(score, 2),
                                    "has_relevant_articles": True
                                })
                    except Exception as e:
                        logger.debug(f"Error checking generated query '{query[:50]}...': {e}")
                        # Все равно добавляем, так как он из KB
                        seen_queries.add(query)
                        relevant_examples.append({
                            "query": query,
                            "score": 0.8,  # Средний score для примеров из KB
                            "has_relevant_articles": True
                        })
        
        # Ограничиваем количество и сортируем по score
        relevant_examples = sorted(relevant_examples, key=lambda x: x["score"], reverse=True)[:limit]
        
        logger.info(f"✅ Generated {len(relevant_examples)} relevant examples")
        
        return {
            "examples": relevant_examples
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения релевантных примеров: {e}", exc_info=True)
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
        
        # Используем выбранную модель, если указана
        if request.llm_provider and request.llm_model:
            # Временно изменяем переменные окружения для использования выбранной модели
            import os
            original_provider = os.environ.get("LLM_PROVIDER")
            original_model = None
            model_env_key = None
            
            # Сохраняем оригинальные значения и устанавливаем новые
            original_timeout = None
            timeout_env_key = None
            
            if request.llm_provider == "openai":
                original_model = os.environ.get("OPENAI_MODEL")
                model_env_key = "OPENAI_MODEL"
                timeout_env_key = "OPENAI_TIMEOUT"
                original_timeout = os.environ.get("OPENAI_TIMEOUT")
                os.environ["LLM_PROVIDER"] = "openai"
                os.environ["OPENAI_MODEL"] = request.llm_model
                if request.llm_timeout:
                    os.environ["OPENAI_TIMEOUT"] = str(request.llm_timeout)
            elif request.llm_provider == "ollama":
                original_model = os.environ.get("OLLAMA_MODEL")
                model_env_key = "OLLAMA_MODEL"
                timeout_env_key = "OLLAMA_TIMEOUT"
                original_timeout = os.environ.get("OLLAMA_TIMEOUT")
                os.environ["LLM_PROVIDER"] = "ollama"
                os.environ["OLLAMA_MODEL"] = request.llm_model
                if request.llm_timeout:
                    os.environ["OLLAMA_TIMEOUT"] = str(request.llm_timeout)
            elif request.llm_provider == "gemini":
                original_model = os.environ.get("GEMINI_MODEL")
                model_env_key = "GEMINI_MODEL"
                timeout_env_key = "GEMINI_TIMEOUT"
                original_timeout = os.environ.get("GEMINI_TIMEOUT")
                os.environ["LLM_PROVIDER"] = "gemini"
                os.environ["GEMINI_MODEL"] = request.llm_model
                if request.llm_timeout:
                    os.environ["GEMINI_TIMEOUT"] = str(request.llm_timeout)
            
            # Сбрасываем синглтон для переинициализации с новыми настройками
            from services.llm_client import reset_llm_client
            reset_llm_client()
            
            try:
                llm_client = get_llm_client(provider=request.llm_provider)
            finally:
                # Восстанавливаем оригинальные значения
                if original_provider:
                    os.environ["LLM_PROVIDER"] = original_provider
                else:
                    os.environ.pop("LLM_PROVIDER", None)
                
                if model_env_key:
                    if original_model:
                        os.environ[model_env_key] = original_model
                    else:
                        os.environ.pop(model_env_key, None)
                
                # Восстанавливаем таймаут
                if timeout_env_key:
                    if original_timeout:
                        os.environ[timeout_env_key] = original_timeout
                    else:
                        os.environ.pop(timeout_env_key, None)
                
                # Восстанавливаем синглтон
                reset_llm_client()
        else:
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
        
        # Получаем таймаут из запроса или используем значение по умолчанию
        llm_timeout = None
        if request.llm_timeout:
            llm_timeout = request.llm_timeout
        elif request.llm_provider:
            # Получаем таймаут из переменных окружения для выбранного провайдера
            import os
            if request.llm_provider == "ollama":
                llm_timeout = int(os.getenv("OLLAMA_TIMEOUT", "500"))
            elif request.llm_provider == "openai":
                llm_timeout = int(os.getenv("OPENAI_TIMEOUT", "600"))
            elif request.llm_provider == "gemini":
                llm_timeout = int(os.getenv("GEMINI_TIMEOUT", "600"))
        
        answer = await llm_client.generate(
            prompt=prompt,
            system_prompt="Ты эксперт по диагностике проблем 3D-печати. Отвечай конкретно и структурированно.",
            timeout=llm_timeout
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
        # Проверяем, является ли это таймаутом
        if "не ответил в течение" in error_msg or "timeout" in error_msg.lower():
            logger.warning(f"⏱️ Таймаут LLM запроса: {e}")
            raise HTTPException(
                status_code=504,
                detail=(
                    f"Превышено время ожидания ответа от LLM. {error_msg} "
                    "Попробуйте увеличить таймаут в настройках или использовать более быструю модель."
                )
            )
        elif "ollama" in error_msg.lower() or "connection refused" in error_msg.lower():
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


@app.post("/api/diagnose/image", response_class=JSONResponse)
async def diagnose_with_image(
    query: str = Body(...),
    printer_model: Optional[str] = Body(None),
    material: Optional[str] = Body(None),
    problem_type: Optional[str] = Body(None),
    conversation_history: Optional[str] = Body(None),  # JSON строка
    image: UploadFile = File(...),
    use_reranking: Optional[str] = Body("true"),  # Строка из form-data
    limit: Optional[str] = Body("5")  # Строка из form-data
):
    """
    Диагностика с анализом изображения дефекта через RetrievalAgent
    
    Использует RetrievalAgent для:
    1. Анализа изображения через Vision Analyzer (Gemini/Ollama)
    2. Извлечения контекста (problem_type, symptoms, description)
    3. Поиска в KB с учетом контекста изображения
    4. Реранкинга результатов для улучшения релевантности
    """
    try:
        # Импортируем RetrievalAgent
        try:
            from app.agents import get_retrieval_agent
        except ImportError:
            logger.error("RetrievalAgent недоступен")
            raise HTTPException(status_code=503, detail="RetrievalAgent не инициализирован")
        
        retrieval_agent = get_retrieval_agent()
        
        # Читаем изображение
        image_data = await image.read()
        
        # Десериализуем conversation_history из JSON строки
        parsed_history = None
        if conversation_history:
            try:
                parsed_history = json.loads(conversation_history)
                if not isinstance(parsed_history, list):
                    parsed_history = None
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Не удалось распарсить conversation_history: {e}")
                parsed_history = None
        
        # Конвертируем строковые параметры в нужные типы
        use_reranking_bool = use_reranking.lower() == "true" if isinstance(use_reranking, str) else bool(use_reranking)
        limit_int = int(limit) if isinstance(limit, str) else limit
        
        # Подготовка фильтров
        filters = {}
        if problem_type:
            filters["problem_type"] = problem_type
        if printer_model:
            filters["printer_models"] = [printer_model]
        if material:
            filters["materials"] = [material]
        
        # Улучшение запроса с учетом истории диалога
        enhanced_query = query
        if parsed_history and len(parsed_history) > 0:
            # Извлекаем предыдущие запросы и ответы из истории
            previous_context = []
            for msg in conversation_history[-3:]:  # Берем последние 3 сообщения
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role == "user" and content:
                        previous_context.append(f"Пользователь: {content}")
                    elif role == "assistant" and content:
                        previous_context.append(f"Система: {content[:200]}...")  # Ограничиваем длину
            
            if previous_context:
                context_text = "\n".join(previous_context)
                enhanced_query = f"{query}\n\nКонтекст предыдущего диалога:\n{context_text}"
                logger.info(f"📝 Запрос улучшен с учетом истории диалога ({len(parsed_history)} сообщений)")
        
        # Поиск с анализом изображения через RetrievalAgent
        logger.info(f"🔍 Поиск с изображением: query='{query}', filters={filters}, history_len={len(parsed_history) if parsed_history else 0}")
        
        search_results = await retrieval_agent.search_with_image(
            query=enhanced_query,
            image_data=image_data,
            filters=filters if filters else None,
            limit=limit_int,
            use_reranking=use_reranking_bool
        )
        
        # Получаем LLM клиент для генерации ответа
        if get_llm_client is None:
            raise HTTPException(status_code=503, detail="LLM сервис не инициализирован")
        
        llm_client = get_llm_client()
        
        # Формирование контекста из найденных статей
        context = ""
        if search_results:
            # Берем топ-3 статьи для контекста
            context_articles = search_results[:3]
            context_parts = []
            for i, article in enumerate(context_articles, 1):
                title = article.get('title', 'Без названия')
                content = article.get('content', '')
                # Берем первые 800 символов контента
                content_preview = content[:800] if len(content) > 800 else content
                if len(content) > 800:
                    content_preview += "..."
                
                article_text = f"Статья {i}: {title}\n{content_preview}"
                
                # Добавляем метаданные если есть
                if article.get('problem_type'):
                    article_text += f"\nТип проблемы: {article.get('problem_type')}"
                if article.get('printer_models'):
                    article_text += f"\nПринтеры: {', '.join(article.get('printer_models', []))}"
                if article.get('materials'):
                    article_text += f"\nМатериалы: {', '.join(article.get('materials', []))}"
                
                context_parts.append(article_text)
            
            context = "\n\n---\n\n".join(context_parts)
        
        # Формирование промпта для LLM
        prompt = f"""Ты эксперт по диагностике проблем 3D-печати. Ты помогаешь пользователям решать их проблемы с эмпатией и пониманием.

ЗАПРОС ПОЛЬЗОВАТЕЛЯ: {query}
"""
        
        # Добавляем контекст из истории диалога, если есть
        if parsed_history and len(parsed_history) > 0:
            history_context = []
            for msg in parsed_history[-3:]:  # Берем последние 3 сообщения
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role == "user" and content:
                        history_context.append(f"Пользователь ранее сказал: {content}")
                    elif role == "assistant" and content:
                        # Берем только краткую информацию из предыдущего ответа
                        history_context.append(f"Ранее было рекомендовано: {content[:150]}...")
            
            if history_context:
                prompt += f"\n\nКОНТЕКСТ ПРЕДЫДУЩЕГО ДИАЛОГА:\n" + "\n".join(history_context)
        
        if printer_model:
            prompt += f"\nМОДЕЛЬ ПРИНТЕРА: {printer_model}"
        
        if material:
            prompt += f"\nМАТЕРИАЛ: {material}"
        
        if problem_type:
            prompt += f"\nТИП ПРОБЛЕМЫ: {problem_type}"
        
        if context:
            prompt += f"\n\nРЕЛЕВАНТНЫЕ СТАТЬИ ИЗ БАЗЫ ЗНАНИЙ:\n{context}"
        
        prompt += """

ЗАДАЧА:
Используй информацию из статей выше, чтобы дать пользователю:
1. Понимание проблемы (что происходит и почему)
2. Конкретные решения с параметрами (температура, скорость, retraction и т.д.)
3. Пошаговые рекомендации

СТИЛЬ ОТВЕТА:
- Будь эмпатичным и понимающим (пользователь столкнулся с проблемой)
- Используй "ты" вместо "вы" для более дружелюбного тона
- Объясняй простым языком, избегая излишнего технического жаргона
- Структурируй ответ: сначала объясни проблему, потом дай решения
- Укажи конкретные параметры (например: "уменьши температуру до 200°C")
- Если нужно - дай несколько вариантов решения

ВАЖНО:
- НЕ просто перечисляй ссылки на статьи
- НЕ копируй текст статей дословно
- ДАЙ человеческий, понятный ответ на основе информации из статей
- Используй информацию из статей как основу, но формулируй своими словами
"""
        
        # Генерация ответа через LLM
        try:
            answer = await llm_client.generate(
                prompt=prompt,
                system_prompt="Ты эксперт по диагностике проблем 3D-печати. Отвечай эмпатично, понятно и конкретно, используя информацию из базы знаний.",
                timeout=600  # Таймаут для LLM
            )
        except Exception as e:
            logger.error(f"Ошибка генерации ответа через LLM: {e}")
            # Fallback: формируем простой ответ на основе статей
            if search_results:
                top_article = search_results[0]
                answer = f"На основе анализа изображения и базы знаний, похоже на проблему: {top_article.get('title', 'stringing')}. "
                if top_article.get('solutions'):
                    answer += "Рекомендации: "
                    for sol in top_article.get('solutions', [])[:3]:
                        answer += f"{sol.get('description', '')}; "
            else:
                answer = "К сожалению, не удалось найти релевантные статьи в базе знаний. Попробуйте описать проблему более подробно."
        
        # Оценка уверенности
        confidence = 0.8 if search_results and search_results[0].get("score", 0) > 0.7 else 0.5
        
        # Определение необходимости уточнений
        needs_clarification = False
        clarification_questions = []
        
        if not printer_model and not any(p in query.lower() for p in ["ender", "prusa", "anycubic", "принтер"]):
            needs_clarification = True
            clarification_questions.append({
                "question": "Какая у вас модель принтера?",
                "question_type": "printer_model",
                "options": None
            })
        
        # Формируем ответ в формате DiagnosticResponse
        return {
            "success": True,
            "answer": answer,
            "query": query,
            "image_name": image.filename,
            "image_size": len(image_data),
            "relevant_articles": search_results[:5],  # Топ-5 статей как источники
            "results_count": len(search_results),
            "confidence": confidence,
            "needs_clarification": needs_clarification,
            "clarification_questions": clarification_questions if needs_clarification else None,
            "image_analysis": True
        }
        
    except Exception as e:
        logger.error(f"Ошибка диагностики с изображением: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка диагностики с изображением: {str(e)}")


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

