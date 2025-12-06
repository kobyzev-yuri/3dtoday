"""
Парсер документов разных форматов для KB
Поддерживает: HTML, PDF, JSON
"""

import os
import logging
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / "config.env")

# Настройка логирования с записью в файл
try:
    from app.utils.logger_config import get_parser_logger
    logger = get_parser_logger()
except ImportError:
    # Fallback если logger_config недоступен
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


class DocumentParser:
    """
    Универсальный парсер документов для KB
    Поддерживает HTML, PDF, JSON
    """
    
    def __init__(self):
        """Инициализация парсера"""
        self.timeout = float(os.getenv("DOCUMENT_PARSER_TIMEOUT", os.getenv("PARSER_TIMEOUT", "30")))
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def parse_document(self, source: str, source_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Парсинг документа из источника
        
        Args:
            source: URL или путь к файлу, или JSON строка
            source_type: Тип источника (auto, html, pdf, json, url)
        
        Returns:
            Словарь с данными документа или None при ошибке
        """
        try:
            # Определение типа источника
            if source_type is None or source_type == "auto":
                source_type = self._detect_source_type(source)
            
            logger.info(f"📥 Парсинг документа типа '{source_type}': {source[:100]}...")
            
            # Парсинг в зависимости от типа
            if source_type == "json":
                return await self._parse_json(source)
            elif source_type == "pdf":
                return await self._parse_pdf(source)
            elif source_type == "html" or source_type == "url":
                return await self._parse_html(source)
            else:
                logger.error(f"❌ Неподдерживаемый тип источника: {source_type}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга документа: {e}", exc_info=True)
            return None
    
    def _detect_source_type(self, source: str) -> str:
        """Автоматическое определение типа источника"""
        # Проверка на JSON строку
        if source.strip().startswith('{') or source.strip().startswith('['):
            try:
                json.loads(source)
                return "json"
            except:
                pass
        
        # Проверка на URL
        parsed = urlparse(source)
        if parsed.scheme in ('http', 'https'):
            if source.lower().endswith('.pdf'):
                return "pdf"
            else:
                return "html"
        
        # Проверка на путь к файлу
        if os.path.exists(source):
            if source.lower().endswith('.pdf'):
                return "pdf"
            elif source.lower().endswith('.json'):
                return "json"
            elif source.lower().endswith(('.html', '.htm')):
                return "html"
        
        # По умолчанию считаем HTML/URL
        return "html"
    
    async def _parse_json(self, source: str) -> Optional[Dict[str, Any]]:
        """Парсинг JSON документа"""
        try:
            # Если это путь к файлу
            if os.path.exists(source):
                with open(source, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                # Если это JSON строка
                data = json.loads(source)
            
            # Валидация формата KB
            if not isinstance(data, dict):
                logger.error("❌ JSON должен быть объектом")
                return None
            
            # Стандартизация формата KB
            article_data = {
                "title": data.get("title", "Без названия"),
                "content": data.get("content", data.get("text", "")),
                "url": data.get("url", ""),
                "section": data.get("section", data.get("category", "unknown")),
                "date": data.get("date", ""),
                "author": data.get("author"),
                "tags": data.get("tags", []),
                "images": data.get("images", []),
                "content_type": data.get("content_type", "article"),  # article, documentation, comparison, technical
                "problem_type": data.get("problem_type"),
                "printer_models": data.get("printer_models", []),
                "materials": data.get("materials", []),
                "symptoms": data.get("symptoms", []),
                "solutions": data.get("solutions", []),
                "metadata": data.get("metadata", {})
            }
            
            logger.info(f"✅ JSON документ распарсен: {article_data['title']}")
            return article_data
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка обработки JSON: {e}")
            return None
    
    async def _parse_pdf(self, source: str) -> Optional[Dict[str, Any]]:
        """Парсинг PDF документа"""
        try:
            # Проверка наличия библиотеки для PDF
            try:
                import PyPDF2
            except ImportError:
                logger.error("❌ PyPDF2 не установлен. Установите: pip install PyPDF2")
                return None
            
            # Скачивание PDF если это URL
            pdf_content = None
            if source.startswith('http'):
                async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                    response = await client.get(source)
                    response.raise_for_status()
                    pdf_content = response.content
            else:
                # Чтение из файла
                with open(source, 'rb') as f:
                    pdf_content = f.read()
            
            if not pdf_content:
                return None
            
            # Парсинг PDF
            import io
            pdf_file = io.BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Извлечение текста
            content_parts = []
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                if text:
                    content_parts.append(text)
            
            content = "\n\n".join(content_parts)
            
            # Извлечение метаданных
            metadata = pdf_reader.metadata or {}
            
            article_data = {
                "title": metadata.get("/Title", Path(source).stem if not source.startswith('http') else "PDF Document"),
                "content": content,
                "url": source if source.startswith('http') else "",
                "section": "Документация",
                "date": metadata.get("/CreationDate", ""),
                "author": metadata.get("/Author"),
                "tags": [],
                "images": [],  # PDF изображения требуют отдельной обработки
                "content_type": "documentation",  # PDF обычно документация
                "metadata": {
                    "pages": len(pdf_reader.pages),
                    "pdf_metadata": dict(metadata)
                }
            }
            
            logger.info(f"✅ PDF документ распарсен: {article_data['title']} ({len(pdf_reader.pages)} страниц)")
            return article_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга PDF: {e}", exc_info=True)
            return None
    
    async def _parse_html(self, source: str) -> Optional[Dict[str, Any]]:
        """Парсинг HTML документа (использует ArticleParser)"""
        try:
            # Проверка типа страницы перед парсингом
            page_type = await self._detect_page_type(source)
            
            if page_type == "questions_list":
                # Это страница со списком вопросов - не парсим как статью
                logger.warning(f"⚠️ URL является списком вопросов, а не статьей: {source}")
                return {
                    "title": "Список вопросов и ответов",
                    "content": "Это страница со списком вопросов. Для добавления в KB используйте URL конкретного вопроса.",
                    "url": source,
                    "section": "Вопросы и ответы",
                    "date": "",
                    "images": [],
                    "content_type": "questions_list",
                    "is_questions_list": True,
                    "error": "Это страница со списком вопросов, а не отдельная статья. Используйте URL конкретного вопроса."
                }
            
            # Импорт парсеров с правильным путем
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            
            # Если это отдельный вопрос, используем QuestionsParser
            if page_type == "question":
                try:
                    from backend.app.services.questions_parser import QuestionsParser
                except ImportError:
                    from app.services.questions_parser import QuestionsParser
                
                parser = QuestionsParser()
                question_data = await parser.parse_question(source)
                
                if question_data:
                    # Преобразуем в формат статьи
                    article_data = {
                        "title": question_data.get("title", ""),
                        "content": question_data.get("content", ""),
                        "url": question_data.get("url", ""),
                        "section": question_data.get("section", "Вопросы и ответы"),
                        "date": question_data.get("date", ""),
                        "author": question_data.get("author"),
                        "tags": question_data.get("tags", []),
                        "images": [],
                        "content_type": "article",  # Вопросы обрабатываем как статьи
                        "question_data": question_data  # Сохраняем оригинальные данные
                    }
                    return article_data
                return None
            
            # Для статей используем ArticleParser
            try:
                from backend.app.services.article_parser import ArticleParser
            except ImportError:
                from app.services.article_parser import ArticleParser
            
            parser = ArticleParser()
            article_data = await parser.parse_article(source)
            
            if article_data:
                # Определение типа контента по содержимому
                content_type = self._detect_content_type(article_data)
                article_data["content_type"] = content_type
            
            return article_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга HTML: {e}", exc_info=True)
            return None
    
    async def _detect_page_type(self, url: str) -> str:
        """
        Определение типа страницы (статья, список вопросов, список статей, отдельный вопрос)
        
        Returns:
            - "questions_list": страница со списком вопросов (/questions)
            - "question": отдельный вопрос (/questions/12345)
            - "blogs_list": страница со списком блогов (/blogs)
            - "article": отдельная статья
        """
        url_lower = url.lower()
        parsed = urlparse(url_lower)
        path = parsed.path.rstrip('/')
        
        # Страницы со списками (без ID в пути)
        if path == "/questions" or path.endswith("/questions"):
            return "questions_list"
        
        if path == "/blogs" or (path.endswith("/blogs") and not path.endswith("/blogs/")):
            return "blogs_list"
        
        # Отдельные вопросы (есть ID в пути)
        if "/questions/" in path:
            # Проверяем, есть ли числовой ID после /questions/
            parts = path.split("/questions/")
            if len(parts) > 1 and parts[1]:
                # Есть что-то после /questions/ - это отдельный вопрос
                return "question"
            else:
                # Нет ID - это список
                return "questions_list"
        
        # Отдельные статьи
        if "/blogs/" in path or "/blog/" in path:
            return "article"
        
        # По умолчанию считаем статьей
        return "article"
    
    def _detect_content_type(self, article_data: Dict[str, Any]) -> str:
        """Определение типа контента по содержимому"""
        title_lower = article_data.get("title", "").lower()
        content_lower = article_data.get("content", "").lower()
        section = article_data.get("section", "").lower()
        
        # Ключевые слова для определения типа
        documentation_keywords = ["документация", "инструкция", "руководство", "manual", "specification"]
        comparison_keywords = ["сравнение", "vs", "versus", "разница", "отличия", "comparison"]
        technical_keywords = ["технические", "характеристики", "параметры", "specs", "technical"]
        problem_keywords = ["проблема", "решение", "исправление", "устранение", "problem", "fix"]
        
        # Проверка по разделу
        if any(kw in section for kw in documentation_keywords):
            return "documentation"
        
        # Проверка по заголовку и содержимому
        text_to_check = title_lower + " " + content_lower[:500]
        
        if any(kw in text_to_check for kw in comparison_keywords):
            return "comparison"
        
        if any(kw in text_to_check for kw in documentation_keywords):
            return "documentation"
        
        if any(kw in text_to_check for kw in technical_keywords):
            return "technical"
        
        if any(kw in text_to_check for kw in problem_keywords):
            return "article"  # Статья о решении проблем
        
        # По умолчанию
        return "article"

