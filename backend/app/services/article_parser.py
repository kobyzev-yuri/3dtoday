"""
Парсер статей с 3dtoday.ru
Скачивает статью по URL и извлекает текст и изображения
"""

import os
import logging
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / "config.env")

logger = logging.getLogger(__name__)


class ArticleParser:
    """
    Парсер статей с сайта 3dtoday.ru
    """
    
    def __init__(self):
        """Инициализация парсера"""
        self.base_url = "https://3dtoday.ru"
        self.timeout = float(os.getenv("ARTICLE_PARSER_TIMEOUT", os.getenv("PARSER_TIMEOUT", "30")))
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def parse_article(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг статьи по URL
        
        Args:
            url: URL статьи на 3dtoday.ru
        
        Returns:
            Словарь с данными статьи или None при ошибке
        """
        try:
            # Проверка URL
            if not url.startswith("http"):
                url = urljoin(self.base_url, url)
            
            logger.info(f"📥 Скачивание статьи: {url}")
            
            # Скачивание HTML
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
            
            # Парсинг HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # Извлечение данных
            article_data = {
                "url": url,
                "title": self._extract_title(soup),
                "content": self._extract_content(soup),
                "section": self._extract_section(soup, url),
                "date": self._extract_date(soup),
                "images": self._extract_images(soup, url),
                "author": self._extract_author(soup),
                "tags": self._extract_tags(soup)
            }
            
            logger.info(f"✅ Статья распарсена: {article_data['title']}")
            return article_data
            
        except httpx.HTTPError as e:
            logger.error(f"❌ Ошибка HTTP при скачивании {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга статьи {url}: {e}", exc_info=True)
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлечение заголовка статьи"""
        # Пробуем разные селекторы
        selectors = [
            'h1.article-title',
            'h1',
            '.article-header h1',
            'title'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title and len(title) > 5:
                    return title
        
        return "Без названия"
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Извлечение содержимого статьи"""
        # Пробуем разные селекторы для контента статей 3dtoday.ru
        selectors = [
            '.blog_post_body',  # Основной контент статей 3dtoday.ru
            '.article-content',
            '.article-text',
            '.post-content',
            '.blog-post-content',
            '.entry-content',
            'article .content',
            'article',
            '.content',
            'main article',
            'main .content',
            '[class*="post"]',
            '[class*="article"]',
            'main div[class*="post"]',
            'main div[class*="content"]'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                # Удаляем скрипты, стили, навигацию, рекламу
                for unwanted in element(["script", "style", "nav", "footer", "aside", "header", 
                                         ".sidebar", ".menu", ".navigation", ".breadcrumbs",
                                         ".advertisement", ".ads", "[class*='ad']"]):
                    unwanted.decompose()
                
                # Извлекаем текст
                content = element.get_text(separator='\n', strip=True)
                if content and len(content) > 100:
                    # Очистка от лишних пробелов и пустых строк
                    content = re.sub(r'\n{3,}', '\n\n', content)
                    # Удаляем строки с навигационными элементами
                    lines = content.split('\n')
                    filtered_lines = []
                    skip_keywords = ['блоги', '3d-моделирование', '3d-печать', 'reprap', 
                                   'акции', 'бизнес', 'новости', 'обзоры', 'применение',
                                   'разное', 'расходные материалы', 'творчество', 'техничка',
                                   '3d-оборудование', '3d-принтеры', '3d-сканеры', '3d-модели',
                                   'войти', 'новости', 'популярное', 'акции', 'объявления',
                                   'вопросы и ответы', 'мы печатаем']
                    
                    for line in lines:
                        line_lower = line.lower().strip()
                        # Пропускаем строки, которые являются навигацией
                        if any(keyword in line_lower for keyword in skip_keywords) and len(line.strip()) < 50:
                            continue
                        # Пропускаем очень короткие строки (вероятно навигация)
                        if len(line.strip()) < 3:
                            continue
                        filtered_lines.append(line)
                    
                    content = '\n'.join(filtered_lines)
                    content = re.sub(r'\n{3,}', '\n\n', content)
                    
                    if len(content) > 100:
                        return content
        
        # Fallback: ищем в main все div с большим количеством текста
        main = soup.find('main')
        if main:
            # Удаляем навигацию из main
            for unwanted in main(["script", "style", "nav", "footer", "aside", "header",
                                 ".sidebar", ".menu", ".navigation", ".breadcrumbs"]):
                unwanted.decompose()
            
            # Ищем самый большой текстовый блок в main
            max_text = ""
            max_len = 0
            
            for div in main.find_all('div', recursive=True):
                text = div.get_text(separator='\n', strip=True)
                # Фильтруем навигацию
                if len(text) > max_len and len(text) > 200:
                    # Проверяем, что это не навигация
                    text_lower = text.lower()
                    nav_indicators = ['блоги', 'войти', 'подписаться', 'отписаться', 
                                    'реклама', 'рекламное объявление']
                    if not any(indicator in text_lower[:200] for indicator in nav_indicators):
                        max_text = text
                        max_len = len(text)
            
            if max_text:
                content = re.sub(r'\n{3,}', '\n\n', max_text)
                if len(content) > 100:
                    return content
            
            # Если не нашли, берем весь main
            content = main.get_text(separator='\n', strip=True)
            content = re.sub(r'\n{3,}', '\n\n', content)
            if len(content) > 100:
                return content
        
        return ""
    
    def _extract_section(self, soup: BeautifulSoup, url: str) -> str:
        """Извлечение раздела статьи на основе структуры 3dtoday.ru"""
        # Проверяем URL для определения раздела
        url_lower = url.lower()
        
        # Специальная обработка для wiki страниц
        if "/wiki/" in url_lower:
            # Это страница из википедии 3D-печати
            if "3dprinter" in url_lower or "принтер" in url_lower:
                return "3D-печать"  # Образовательная статья
            elif "material" in url_lower or "материал" in url_lower or "filament" in url_lower:
                return "Расходные материалы"
            elif "equipment" in url_lower or "оборудование" in url_lower:
                return "Оборудование"
            elif "problem" in url_lower or "проблем" in url_lower or "issue" in url_lower:
                return "Техничка"
            else:
                return "3D-печать"  # По умолчанию для вики
        
        # Пробуем извлечь из breadcrumbs или URL
        breadcrumbs = soup.select('.breadcrumbs a, .breadcrumb a, nav a')
        if breadcrumbs:
            for crumb in breadcrumbs:
                text = crumb.get_text(strip=True)
                # Основные разделы KB на основе 3dtoday.ru
                if text in ["Техничка", "3D-печать", "Оборудование", "Расходные материалы", 
                           "Применение", "Обзоры", "3D-моделирование", "RepRap"]:
                    return text
        
        # Извлечение из URL (структура 3dtoday.ru)
        url_lower = url.lower()
        
        if "/we-print/" in url_lower or "/we_print/" in url_lower:
            return "Применение"  # "Мы печатаем" относится к применению 3D-печати
        elif "/technical/" in url_lower or "/tech/" in url_lower or "техничка" in url_lower:
            return "Техничка"
        elif "/equipment/" in url_lower or "/printer/" in url_lower or "оборудование" in url_lower:
            return "Оборудование"
        elif "/material/" in url_lower or "материал" in url_lower or "расходные" in url_lower:
            return "Расходные материалы"
        elif "/application/" in url_lower or "применение" in url_lower:
            return "Применение"
        elif "/review/" in url_lower or "обзор" in url_lower:
            return "Обзоры"
        elif "/print/" in url_lower or "/printing/" in url_lower or "печать" in url_lower:
            return "3D-печать"
        elif "/blogs/" in url_lower or "/blog/" in url_lower:
            # Пытаемся определить раздел из breadcrumbs или категорий
            blog_categories = soup.select('.blog-category, .category, .tag')
            for cat in blog_categories:
                cat_text = cat.get_text(strip=True)
                if cat_text in ["Техничка", "3D-печать", "Оборудование", "Расходные материалы", 
                               "Применение", "Обзоры", "3D-моделирование", "RepRap"]:
                    return cat_text
            return "3D-печать"  # По умолчанию для блогов
        elif "/model/" in url_lower or "модель" in url_lower:
            return "3D-моделирование"
        elif "/reprap/" in url_lower:
            return "RepRap"
        
        return "unknown"
    
    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Извлечение даты публикации"""
        # Пробуем разные селекторы
        selectors = [
            '.article-date',
            '.post-date',
            'time[datetime]',
            '.date'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                date = element.get('datetime') or element.get_text(strip=True)
                if date:
                    return date
        
        return ""
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """Извлечение изображений из статьи"""
        images = []
        
        # Ищем изображения в контенте статьи
        img_tags = soup.select('.article-content img, .article-text img, article img')
        
        for img in img_tags:
            src = img.get('src') or img.get('data-src')
            if not src:
                continue
            
            # Преобразуем относительные URL в абсолютные
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = urljoin(base_url, src)
            elif not src.startswith('http'):
                src = urljoin(base_url, src)
            
            alt = img.get('alt', '')
            title = img.get('title', '')
            
            images.append({
                "url": src,
                "alt": alt,
                "title": title,
                "description": alt or title or ""
            })
        
        return images
    
    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение автора статьи"""
        selectors = [
            '.article-author',
            '.author',
            '.post-author'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        
        return None
    
    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """Извлечение тегов статьи"""
        tags = []
        
        tag_elements = soup.select('.tags a, .tag a, .article-tags a')
        for tag_elem in tag_elements:
            tag = tag_elem.get_text(strip=True)
            if tag:
                tags.append(tag)
        
        return tags

