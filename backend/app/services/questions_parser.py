"""
Парсер для страниц вопросов и ответов с 3dtoday.ru
Обрабатывает отдельные вопросы и ответы на них
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


class QuestionsParser:
    """
    Парсер для вопросов и ответов с 3dtoday.ru
    """
    
    def __init__(self):
        """Инициализация парсера"""
        self.base_url = "https://3dtoday.ru"
        self.timeout = float(os.getenv("QUESTIONS_PARSER_TIMEOUT", os.getenv("PARSER_TIMEOUT", "30")))
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def parse_question(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг отдельного вопроса по URL
        
        Args:
            url: URL вопроса на 3dtoday.ru/questions/...
        
        Returns:
            Словарь с данными вопроса и ответов или None при ошибке
        """
        try:
            # Проверка URL
            if not url.startswith("http"):
                url = urljoin(self.base_url, url)
            
            logger.info(f"📥 Скачивание вопроса: {url}")
            
            # Скачивание HTML
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
            
            # Парсинг HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # Извлечение данных вопроса
            question_data = {
                "url": url,
                "title": self._extract_question_title(soup),
                "question": self._extract_question_text(soup),
                "answers": self._extract_answers(soup),
                "author": self._extract_question_author(soup),
                "date": self._extract_question_date(soup),
                "tags": self._extract_question_tags(soup),
                "section": "Вопросы и ответы"
            }
            
            # Формирование контента из вопроса и ответов
            content_parts = [f"Вопрос: {question_data['question']}"]
            if question_data.get('answers'):
                content_parts.append("\nОтветы:")
                for i, answer in enumerate(question_data['answers'], 1):
                    content_parts.append(f"\nОтвет {i}: {answer.get('text', '')}")
            
            question_data["content"] = "\n".join(content_parts)
            
            logger.info(f"✅ Вопрос распарсен: {question_data['title']} ({len(question_data.get('answers', []))} ответов)")
            return question_data
            
        except httpx.HTTPError as e:
            logger.error(f"❌ Ошибка HTTP при скачивании {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга вопроса {url}: {e}", exc_info=True)
            return None
    
    def _extract_question_title(self, soup: BeautifulSoup) -> str:
        """Извлечение заголовка вопроса"""
        selectors = [
            'h1.question-title',
            '.question-header h1',
            'h1',
            'title'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title and len(title) > 5:
                    # Убираем лишнее из title
                    if "3D Today" in title:
                        title = title.split("3D Today")[0].strip()
                    return title
        
        return "Без названия"
    
    def _extract_question_text(self, soup: BeautifulSoup) -> str:
        """Извлечение текста вопроса"""
        selectors = [
            '.question-text',
            '.question-content',
            '.question-body',
            'article.question',
            'h1 + p',  # Параграф после заголовка
            'h1 ~ p',  # Параграфы после заголовка
            'main p',  # Параграфы в main
            '#question-content',
            '.content p'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                # Удаляем скрипты и стили
                for script in element(["script", "style"]):
                    script.decompose()
                
                text = element.get_text(separator='\n', strip=True)
                if text and len(text) > 20:
                    return re.sub(r'\n{3,}', '\n\n', text)
        
        # Fallback: ищем все параграфы после h1
        h1 = soup.find('h1')
        if h1:
            # Ищем следующий параграф
            next_p = h1.find_next_sibling('p')
            if next_p:
                text = next_p.get_text(separator='\n', strip=True)
                if text and len(text) > 20:
                    return re.sub(r'\n{3,}', '\n\n', text)
            
            # Или берем все параграфы после h1 до следующего заголовка
            content_parts = []
            for elem in h1.find_next_siblings():
                if elem.name == 'h2' or elem.name == 'h3':
                    break
                if elem.name == 'p':
                    text = elem.get_text(strip=True)
                    if text:
                        content_parts.append(text)
            
            if content_parts:
                return '\n'.join(content_parts)
        
        return ""
    
    def _extract_answers(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Извлечение ответов на вопрос"""
        answers = []
        
        # Пробуем разные селекторы для ответов
        answer_elements = soup.select('.answer, .answer-item, .comment-answer, article.answer')
        
        for elem in answer_elements:
            # Удаляем скрипты и стили
            for script in elem(["script", "style"]):
                script.decompose()
            
            answer_text = elem.get_text(separator='\n', strip=True)
            if answer_text and len(answer_text) > 20:
                answer_author = self._extract_answer_author(elem)
                answer_date = self._extract_answer_date(elem)
                
                answers.append({
                    "text": answer_text,
                    "author": answer_author,
                    "date": answer_date
                })
        
        return answers
    
    def _extract_question_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение автора вопроса"""
        selectors = [
            '.question-author',
            '.author',
            '.question-meta .author'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        
        return None
    
    def _extract_answer_author(self, answer_elem: BeautifulSoup) -> Optional[str]:
        """Извлечение автора ответа"""
        author_elem = answer_elem.select_one('.answer-author, .author, .comment-author')
        if author_elem:
            return author_elem.get_text(strip=True)
        return None
    
    def _extract_question_date(self, soup: BeautifulSoup) -> str:
        """Извлечение даты вопроса"""
        selectors = [
            '.question-date',
            '.date',
            '.question-meta .date',
            'time[datetime]'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                date = element.get('datetime') or element.get_text(strip=True)
                if date:
                    return date
        
        return ""
    
    def _extract_answer_date(self, answer_elem: BeautifulSoup) -> str:
        """Извлечение даты ответа"""
        date_elem = answer_elem.select_one('.answer-date, .date, time[datetime]')
        if date_elem:
            return date_elem.get('datetime') or date_elem.get_text(strip=True)
        return ""
    
    def _extract_question_tags(self, soup: BeautifulSoup) -> List[str]:
        """Извлечение тегов вопроса"""
        tags = []
        
        tag_elements = soup.select('.question-tags a, .tags a, .tag')
        for tag_elem in tag_elements:
            tag = tag_elem.get_text(strip=True)
            if tag:
                tags.append(tag)
        
        return tags

