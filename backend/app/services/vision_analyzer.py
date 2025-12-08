"""
Vision Analyzer для анализа изображений через Gemini Vision API
Адаптировано из ai_billing проекта
"""

import os
import logging
import httpx
import base64
from typing import Dict, Any, Optional, List
from pathlib import Path
from PIL import Image
import io
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / "config.env")

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    """
    Анализатор изображений через Gemini Vision API
    Используется для анализа изображений из PDF и проверки их релевантности
    """
    
    def __init__(self):
        """Инициализация Vision Analyzer"""
        self.proxy_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("PROXYAPI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.gemini_base_url = os.getenv("GEMINI_BASE_URL", "https://api.proxyapi.ru/google")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
        self.use_gemini = bool(self.proxy_api_key)
        
        if not self.use_gemini:
            logger.warning("⚠️ Gemini Vision API не настроен - требуется GEMINI_API_KEY или PROXYAPI_API_KEY")
    
    def check_availability(self) -> Dict[str, Any]:
        """Проверка доступности Gemini Vision API"""
        if not self.use_gemini:
            return {
                'available': False,
                'message': 'Gemini Vision API не настроен - требуется GEMINI_API_KEY'
            }
        
        try:
            # Простая проверка доступности API
            return {
                'available': True,
                'message': f'Google Gemini {self.gemini_model} доступен через ProxyAPI'
            }
        except Exception as e:
            return {
                'available': False,
                'message': f'Ошибка проверки доступности Gemini: {e}'
            }
    
    def analyze_image(self, image_data: bytes, image_name: str = "image") -> Dict[str, Any]:
        """
        Анализ изображения через Gemini Vision API
        
        Args:
            image_data: Байты изображения
            image_name: Имя изображения для контекста
        
        Returns:
            Dict с результатами анализа
        """
        if not self.use_gemini:
            return {
                'success': False,
                'error': 'Google Gemini не настроен - требуется GEMINI_API_KEY',
                'provider': 'gemini'
            }
        
        try:
            # Оптимизируем изображение для больших файлов
            try:
                image = Image.open(io.BytesIO(image_data))
                
                # Для больших изображений используем умное масштабирование
                file_size = len(image_data)
                max_size = 2048 if file_size > 5 * 1024 * 1024 else 1024
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Конвертируем в RGB если нужно
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Сохраняем в буфер с оптимальным качеством
                img_buffer = io.BytesIO()
                quality = 90 if file_size > 2 * 1024 * 1024 else 85
                image.save(img_buffer, format='JPEG', quality=quality)
                img_data = img_buffer.getvalue()
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Ошибка обработки изображения: {e}'
                }
            
            # Кодируем в base64
            image_base64 = base64.b64encode(img_data).decode()
            
            return self._analyze_with_gemini(image_base64, image_name)
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа изображения: {e}")
            return {
                'success': False,
                'error': f'Ошибка анализа изображения: {e}'
            }
    
    def analyze_image_from_path(self, image_path: Path) -> Dict[str, Any]:
        """
        Анализ изображения из файла
        
        Args:
            image_path: Путь к файлу изображения
        
        Returns:
            Dict с результатами анализа
        """
        try:
            # Проверяем размер файла
            file_size = image_path.stat().st_size
            if file_size > 20 * 1024 * 1024:  # 20MB лимит
                return {
                    'success': False,
                    'error': f'Изображение слишком большое: {file_size / 1024 / 1024:.1f}MB'
                }
            
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            return self.analyze_image(image_data, image_path.name)
            
        except Exception as e:
            logger.error(f"❌ Ошибка чтения изображения {image_path}: {e}")
            return {
                'success': False,
                'error': f'Ошибка чтения изображения: {e}'
            }
    
    def analyze_image_from_base64(self, image_base64: str, image_name: str = "image") -> Dict[str, Any]:
        """
        Анализ изображения из base64 строки
        
        Args:
            image_base64: Base64 строка изображения
            image_name: Имя изображения для контекста
        
        Returns:
            Dict с результатами анализа
        """
        try:
            image_data = base64.b64decode(image_base64)
            return self.analyze_image(image_data, image_name)
        except Exception as e:
            logger.error(f"❌ Ошибка декодирования base64: {e}")
            return {
                'success': False,
                'error': f'Ошибка декодирования base64: {e}'
            }
    
    def check_relevance_to_3d_printing(self, image_analysis: str, image_name: str = "image") -> Dict[str, Any]:
        """
        Проверка релевантности изображения к теме 3D-печати
        
        Args:
            image_analysis: Текст анализа изображения от Gemini
            image_name: Имя изображения для контекста
        
        Returns:
            Dict с оценкой релевантности
        """
        if not self.use_gemini:
            return {
                'success': False,
                'error': 'Gemini не настроен для проверки релевантности'
            }
        
        prompt = f"""Проанализируй описание изображения '{image_name}' и определи, релевантно ли оно теме 3D-печати.

ОПИСАНИЕ ИЗОБРАЖЕНИЯ:
{image_analysis}

ЗАДАЧА:
Определи, связано ли изображение с 3D-печатью, 3D-принтерами, проблемами печати, материалами для 3D-печати, или это нерелевантный контент.

Верни ТОЛЬКО валидный JSON:
{{
    "is_relevant": true/false,
    "relevance_score": 0.0-1.0,
    "reason": "краткое объяснение",
    "related_topics": ["тема1", "тема2"] или [],
    "problem_type": "тип проблемы" или null,
    "printer_models": ["модель1"] или [],
    "materials": ["материал1"] или []
}}
"""
        
        try:
            response = httpx.post(
                f"{self.gemini_base_url}/v1/models/{self.gemini_model}:generateContent",
                headers={
                    "Authorization": f"Bearer {self.proxy_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "contents": [{
                        "parts": [{
                            "text": prompt
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 500
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    response_text = result['candidates'][0]['content']['parts'][0]['text']
                    
                    # Извлекаем JSON из ответа
                    import json
                    import re
                    
                    # Пытаемся найти JSON в ответе
                    json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                    if json_match:
                        try:
                            relevance_data = json.loads(json_match.group())
                            return {
                                'success': True,
                                **relevance_data
                            }
                        except json.JSONDecodeError:
                            pass
                    
                    # Если не удалось распарсить JSON, используем простую эвристику
                    analysis_lower = image_analysis.lower()
                    relevant_keywords = ['3d', 'принтер', 'печать', 'filament', 'pla', 'petg', 'abs', 'printer', 'extruder', 'bed', 'nozzle', 'layer', 'stringing', 'warping']
                    is_relevant = any(keyword in analysis_lower for keyword in relevant_keywords)
                    
                    return {
                        'success': True,
                        'is_relevant': is_relevant,
                        'relevance_score': 0.7 if is_relevant else 0.2,
                        'reason': 'Определено по ключевым словам',
                        'related_topics': [],
                        'problem_type': None,
                        'printer_models': [],
                        'materials': []
                    }
                else:
                    raise Exception(f'Неожиданный формат ответа Gemini: {result}')
            else:
                raise Exception(f'Gemini API error: {response.status_code} - {response.text}')
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки релевантности: {e}")
            return {
                'success': False,
                'error': f'Ошибка проверки релевантности: {e}'
            }
    
    def _analyze_with_gemini(self, image_data: str, image_name: str) -> Dict[str, Any]:
        """Анализ изображения с помощью Google Gemini через ProxyAPI"""
        headers = {
            "Authorization": f"Bearer {self.proxy_api_key}",
            "Content-Type": "application/json"
        }
        
        # Промпт для анализа изображений из PDF документов о 3D-печати
        prompt = f"""Проанализируй это изображение из документа '{image_name}' детально.

Для изображений из PDF документов о 3D-печати:
1. Опиши общую структуру и компоновку
2. Извлеки весь видимый текст (сохрани форматирование)
3. Определи тип контента (техническая схема, инструкция, пример проблемы, сравнение и т.д.)
4. Выдели ключевые разделы, заголовки, таблицы
5. Опиши схемы, диаграммы, графики если есть
6. Укажи важные технические характеристики или данные
7. Определи, связано ли изображение с 3D-печатью, принтерами, материалами или проблемами печати

Ответь подробно на русском языке, сохраняя структуру документа."""
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        },
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1500
            }
        }
        
        try:
            response = httpx.post(
                f"{self.gemini_base_url}/v1/models/{self.gemini_model}:generateContent",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    analysis_text = result['candidates'][0]['content']['parts'][0]['text']
                    return {
                        'success': True,
                        'analysis': analysis_text,
                        'model': self.gemini_model,
                        'provider': 'gemini'
                    }
                else:
                    raise Exception(f'Неожиданный формат ответа Gemini: {result}')
            else:
                raise Exception(f'Gemini API error: {response.status_code} - {response.text}')
                
        except Exception as e:
            logger.error(f"❌ Ошибка анализа через Gemini: {e}")
            return {
                'success': False,
                'error': f'Ошибка анализа через Gemini: {e}',
                'provider': 'gemini'
            }
