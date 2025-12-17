"""
Сервис для анализа URL через LLM с Function Calling
Позволяет GPT-4o и Gemini 3 самим загружать и анализировать контент
"""

import os
import logging
import httpx
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / "config.env")

logger = logging.getLogger(__name__)


class LLMURLAnalyzer:
    """
    Анализатор URL через LLM с Function Calling
    LLM сам загружает контент и формирует JSON для KB
    """
    
    def __init__(self, llm_provider: Optional[str] = None, model: Optional[str] = None, timeout: Optional[int] = None):
        """
        Инициализация анализатора
        
        Args:
            llm_provider: Провайдер LLM (openai, gemini)
            model: Модель для использования
            timeout: Таймаут для LLM запросов в секундах (опционально)
        """
        self.llm_provider = llm_provider or os.getenv("LLM_PROVIDER", "openai").lower()
        self.model = model or self._get_default_model()
        
        # Используем переданный таймаут или значение из переменных окружения
        if timeout is not None:
            self.timeout = timeout
        elif self.llm_provider == "openai":
            self.timeout = int(os.getenv("OPENAI_TIMEOUT", "120"))
        else:
            self.timeout = int(os.getenv("GEMINI_TIMEOUT", "120"))
        
        logger.info(f"🔧 LLMURLAnalyzer инициализирован: provider={self.llm_provider}, model={self.model}, timeout={self.timeout}s")
    
    def _get_default_model(self) -> str:
        """Получение модели по умолчанию для провайдера"""
        if self.llm_provider == "openai":
            return os.getenv("OPENAI_MODEL", "gpt-4o")
        elif self.llm_provider == "gemini":
            return os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
        else:
            raise ValueError(f"Неподдерживаемый провайдер: {self.llm_provider}")
    
    async def analyze_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Анализ URL через LLM с Function Calling
        
        LLM сам загружает контент и формирует структурированный JSON для KB
        
        Args:
            url: URL для анализа
        
        Returns:
            Словарь с данными статьи в формате KB или None при ошибке
        """
        try:
            logger.info(f"🔍 Анализ URL через {self.llm_provider} ({self.model}): {url}")
            
            if self.llm_provider == "openai":
                return await self._analyze_with_openai(url)
            elif self.llm_provider == "gemini":
                return await self._analyze_with_gemini(url)
            else:
                raise ValueError(f"Неподдерживаемый провайдер: {self.llm_provider}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка анализа URL: {e}", exc_info=True)
            return None
    
    async def _analyze_with_openai(self, url: str) -> Optional[Dict[str, Any]]:
        """Анализ через OpenAI GPT-4o с Function Calling"""
        try:
            from openai import OpenAI
            
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")
            
            if not api_key:
                raise ValueError("OPENAI_API_KEY не установлен")
            
            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=self.timeout
            )
            
            # Определяем функцию для загрузки URL
            fetch_url_function = {
                "type": "function",
                "function": {
                    "name": "fetch_url_content",
                    "description": "Загружает содержимое веб-страницы по URL и возвращает HTML контент",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "URL веб-страницы для загрузки"
                            }
                        },
                        "required": ["url"]
                    }
                }
            }
            
            # Системный промпт
            system_prompt = """Ты умный библиотекарь для базы знаний по 3D-печати.

Твоя задача:
1. Используй функцию fetch_url_content для загрузки содержимого страницы
2. Проанализируй загруженный контент (текст и изображения)
3. Определи релевантность для темы 3D-печати и решения проблем
4. Сформируй структурированный JSON в следующем формате:

{
    "title": "Заголовок статьи",
    "content": "Основное содержимое (без навигации, рекламы, воды)",
    "url": "URL статьи",
    "section": "Раздел (Техничка, Оборудование, Расходные материалы, Применение, 3D-печать, Обзоры, 3D-моделирование, RepRap, Вопросы и ответы)",
    "content_type": "article|documentation|comparison|technical",
    "relevance_score": 0.0-1.0,
    "quality_score": 0.0-1.0,
    "is_relevant": true/false,
    "abstract": "Краткое изложение (2-3 предложения)",
    "problem": "Описание проблемы (если это статья о решении проблемы)",
    "symptoms": ["симптом1", "симптом2"],
    "solutions": [
        {
            "description": "Описание решения",
            "parameters": {"параметр": "значение"}
        }
    ],
    "printer_models": ["модель1", "модель2"],
    "materials": ["PLA", "PETG"],
    "images": [
        {
            "url": "URL изображения",
            "alt": "Описание",
            "description": "Анализ изображения"
        }
    ],
    "date": "Дата публикации",
    "author": "Автор (если есть)",
    "tags": ["тег1", "тег2"]
}

ВАЖНО:
- Отклоняй контент не по теме (музыка, личные предпочтения, оффтоп)
- Извлекай только полезную техническую информацию
- Удаляй навигацию, рекламу, комментарии
- Фокусируйся на проблемах 3D-печати и их решениях
- Для изображений: анализируй визуальные индикаторы проблем/решений

Верни ТОЛЬКО валидный JSON, без дополнительного текста."""
            
            # Пользовательский промпт
            user_prompt = f"""Проанализируй эту страницу и создай структурированный JSON для базы знаний:

URL: {url}

Используй функцию fetch_url_content для загрузки контента, затем проанализируй его и верни JSON в указанном формате."""
            
            # Вызов с Function Calling
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            logger.debug(f"📤 Отправка запроса к OpenAI с Function Calling...")
            
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[fetch_url_function],
                tool_choice="auto",  # Модель сама решает, использовать ли функцию
                temperature=0.2,
                max_tokens=4000
            )
            
            # Обработка ответа
            message = response.choices[0].message
            
            # Если модель вызвала функцию, выполняем её
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "fetch_url_content":
                        # Выполняем функцию загрузки URL
                        import json as json_lib
                        function_args = json_lib.loads(tool_call.function.arguments)
                        fetched_url = function_args.get("url", url)
                        
                        logger.info(f"📥 LLM запросил загрузку URL: {fetched_url}")
                        
                        # Загружаем контент
                        async with httpx.AsyncClient(timeout=self.timeout) as http_client:
                            http_response = await http_client.get(fetched_url, headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                            })
                            html_content = http_response.text
                        
                        # Добавляем результат функции в сообщения
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"Контент страницы загружен. HTML длина: {len(html_content)} символов.\n\n{html_content[:50000]}"  # Ограничиваем размер
                        })
                        
                        # Повторный запрос с загруженным контентом
                        logger.debug(f"📤 Повторный запрос с загруженным контентом...")
                        # Создаем новый список сообщений без tool calls для финального запроса
                        final_messages = [
                            messages[0],  # Системный промпт
                            messages[1],  # Первый запрос пользователя
                            {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [tool_call]
                            },
                            messages[-1]  # Результат функции
                        ]
                        response = client.chat.completions.create(
                            model=self.model,
                            messages=final_messages,
                            temperature=0.2,
                            max_tokens=4000
                        )
                        message = response.choices[0].message
            
            # Извлекаем JSON из ответа
            content = message.content
            logger.debug(f"📥 Получен ответ от OpenAI ({len(content)} символов)")
            
            # Парсим JSON
            json_data = self._extract_json(content)
            
            if json_data:
                logger.info(f"✅ URL успешно проанализирован через OpenAI")
                return json_data
            else:
                logger.warning(f"⚠️ Не удалось извлечь JSON из ответа")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка анализа через OpenAI: {e}", exc_info=True)
            return None
    
    async def _analyze_with_gemini(self, url: str) -> Optional[Dict[str, Any]]:
        """Анализ через Google Gemini 3 через ProxyAPI.ru REST API"""
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            base_url = os.getenv("GEMINI_BASE_URL", "https://api.proxyapi.ru/google")
            
            if not api_key:
                raise ValueError("GEMINI_API_KEY не установлен")
            
            # Загружаем контент страницы заранее
            async with httpx.AsyncClient(timeout=self.timeout) as http_client:
                http_response = await http_client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                html_content = http_response.text
            
            # Системный промпт
            system_instruction = """Ты умный библиотекарь для базы знаний по 3D-печати.

Твоя задача:
1. Проанализируй загруженный контент (текст и изображения)
2. Определи релевантность для темы 3D-печати и решения проблем
3. Сформируй структурированный JSON в следующем формате:

{
    "title": "Заголовок статьи",
    "content": "Основное содержимое (без навигации, рекламы, воды)",
    "url": "URL статьи",
    "section": "Раздел (3D-печать, Оборудование, Расходные материалы, Техничка, Применение, Обзоры)",
    "content_type": "article|documentation|comparison|technical",
    "relevance_score": 0.0-1.0,
    "quality_score": 0.0-1.0,
    "is_relevant": true/false,
    "abstract": "Краткое изложение",
    "problem": "Описание проблемы (если есть)",
    "symptoms": ["симптом1"],
    "solutions": [{"description": "...", "parameters": {}}],
    "printer_models": ["модель1"],
    "materials": ["PLA"],
    "images": [{"url": "...", "alt": "...", "description": "..."}],
    "date": "Дата",
    "author": "Автор",
    "tags": ["тег1"]
}

ВАЖНО: 
- Образовательные статьи о 3D-печати (например, "Что такое 3D-принтер") РЕЛЕВАНТНЫ и должны получать relevance_score >= 0.7
- Отклоняй только контент не связанный с 3D-печатью
- Верни ТОЛЬКО валидный JSON."""
            
            # Пользовательский промпт
            user_prompt = f"""Проанализируй эту страницу и создай структурированный JSON для базы знаний:

URL: {url}

Загруженный HTML контент:
{html_content[:50000]}

Верни JSON в указанном формате."""
            
            logger.debug(f"📤 Отправка запроса к Gemini через ProxyAPI...")
            
            # Используем REST API ProxyAPI.ru
            request_data = {
                "contents": [{
                    "parts": [{"text": user_prompt}]
                }],
                "systemInstruction": {
                    "parts": [{"text": system_instruction}]
                },
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 4000,
                }
            }
            
            model_endpoint = f"/v1beta/models/{self.model}:generateContent"
            
            async with httpx.AsyncClient(
                base_url=base_url.rstrip('/'),
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            ) as client:
                response = await client.post(model_endpoint, json=request_data)
                response.raise_for_status()
                
                result = response.json()
                
                # Извлекаем текст из ответа
                candidates = result.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        text = parts[0].get("text", "")
                        if text:
                            logger.debug(f"📥 Получен ответ от Gemini ({len(text)} символов)")
                            
                            # Извлекаем JSON
                            json_data = self._extract_json(text)
                            
                            if json_data:
                                logger.info(f"✅ URL успешно проанализирован через Gemini")
                                return json_data
                            else:
                                logger.warning(f"⚠️ Не удалось извлечь JSON из ответа")
                                return None
                
                raise Exception("Пустой ответ от Gemini")
                
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP ошибка Gemini: {e.response.status_code if hasattr(e, 'response') else 'unknown'} - {e.response.text[:200] if hasattr(e, 'response') else str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка анализа через Gemini: {e}", exc_info=True)
            return None
    
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Извлечение JSON из текста ответа LLM"""
        try:
            # Пытаемся найти JSON в тексте
            import re
            
            # Ищем JSON блок
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
            
            # Если не нашли, пытаемся распарсить весь текст
            return json.loads(text.strip())
            
        except json.JSONDecodeError:
            logger.warning(f"⚠️ Не удалось распарсить JSON из текста")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения JSON: {e}")
            return None

