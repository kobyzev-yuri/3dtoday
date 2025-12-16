"""
Универсальный клиент для LLM (Ollama и ProxyAPI/OpenAI)
"""

import os
import logging
import httpx
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / "config.env")

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Универсальный клиент для работы с LLM (Ollama, OpenAI или Gemini)
    """
    
    def __init__(self, provider: Optional[str] = None):
        """
        Инициализация клиента на основе конфигурации
        
        Args:
            provider: Провайдер LLM (openai, ollama, gemini). Если не указан, используется из config.env
        """
        self.provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Инициализация клиента в зависимости от провайдера с автоматическим fallback"""
        providers_to_try = []
        
        # Определяем порядок попыток инициализации
        if self.provider == "ollama":
            providers_to_try = ["ollama", "gemini", "openai"]
        elif self.provider == "gemini":
            providers_to_try = ["gemini", "openai", "ollama"]
        elif self.provider == "openai":
            providers_to_try = ["openai", "gemini", "ollama"]
        else:
            # По умолчанию пробуем все провайдеры в порядке приоритета
            providers_to_try = ["gemini", "openai", "ollama"]
        
        last_error = None
        for provider in providers_to_try:
            try:
                if provider == "ollama":
                    self._init_ollama()
                elif provider == "openai":
                    self._init_openai()
                elif provider == "gemini":
                    self._init_gemini()
                else:
                    continue
                
                # Если инициализация успешна, обновляем провайдер
                if provider != self.provider:
                    logger.info(f"✅ Используется провайдер {provider} (вместо {self.provider})")
                    self.provider = provider
                return
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Не удалось инициализировать {provider}: {e}")
                continue
        
        # Если все провайдеры недоступны
        error_msg = f"Не удалось инициализировать ни один LLM провайдер. Последняя ошибка: {last_error}"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)
    
    def _get_available_models(self) -> List[str]:
        """Получение списка доступных моделей Ollama"""
        try:
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            response = httpx.get(f"{ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except Exception:
            return []
    
    def _init_ollama(self):
        """Инициализация Ollama клиента"""
        try:
            self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            configured_model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
            
            # Проверяем доступность модели, если нет - используем первую доступную qwen или первую в списке
            try:
                available_models = self._get_available_models()
                if available_models:
                    # Предпочитаем qwen модели
                    qwen_models = [m for m in available_models if 'qwen' in m.lower()]
                    preferred_models = qwen_models if qwen_models else available_models
                    
                    if configured_model not in available_models:
                        fallback_model = preferred_models[0] if preferred_models else available_models[0]
                        logger.warning(f"⚠️ Модель '{configured_model}' не найдена. Используем '{fallback_model}'")
                        self.model = fallback_model
                    else:
                        self.model = configured_model
                        logger.info(f"✅ Используется модель Ollama: {self.model}")
                else:
                    logger.warning(f"⚠️ Не удалось получить список моделей. Используем '{configured_model}'")
                    self.model = configured_model
            except Exception as e:
                logger.warning(f"⚠️ Не удалось проверить доступные модели: {e}. Используем '{configured_model}'")
                self.model = configured_model
            
            self.temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
            self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "500"))
            
            # Проверка доступности Ollama (не критично, если есть fallback)
            if not self._check_ollama_available():
                raise ConnectionError(f"Ollama недоступен по адресу {self.ollama_url}")
            
            # Создаем клиент без таймаута по умолчанию, 
            # таймаут будет передаваться в каждый запрос
            self.client = httpx.AsyncClient(
                base_url=self.ollama_url,
                timeout=None  # Таймаут будет задаваться в каждом запросе
            )
            
            logger.info(f"✅ Ollama клиент инициализирован (model={self.model}, url={self.ollama_url})")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Ollama: {e}")
            raise
    
    def _init_openai(self):
        """Инициализация OpenAI/ProxyAPI клиента"""
        try:
            from openai import OpenAI
            
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
            self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
            self.timeout = int(os.getenv("OPENAI_TIMEOUT", "600"))
            
            if not api_key:
                raise ValueError("OPENAI_API_KEY не установлен в config.env")
            
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=self.timeout
            )
            
            logger.info(f"✅ OpenAI/ProxyAPI клиент инициализирован (model={self.model})")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации OpenAI: {e}")
            raise
    
    def _init_gemini(self):
        """Инициализация Gemini/ProxyAPI клиента через REST API"""
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            base_url = os.getenv("GEMINI_BASE_URL", "https://api.proxyapi.ru/google")
            self.model = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
            self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))
            self.timeout = int(os.getenv("GEMINI_TIMEOUT", "120"))
            
            if not api_key:
                raise ValueError("GEMINI_API_KEY не установлен в config.env")
            
            # ProxyAPI.ru использует REST API напрямую
            # Формат: https://api.proxyapi.ru/google/v1beta/models/{model}:generateContent
            self.api_key = api_key
            self.base_url = base_url.rstrip('/')
            
            # Создаем HTTP клиент для ProxyAPI
            # Таймаут будет передаваться в каждый запрос
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=None,  # Таймаут будет задаваться в каждом запросе
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            
            logger.info(f"✅ Gemini/ProxyAPI клиент инициализирован (model={self.model}, base_url={self.base_url})")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Gemini: {e}")
            raise
    
    def _check_ollama_available(self):
        """Проверка доступности Ollama сервера"""
        try:
            response = httpx.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Ollama сервер доступен")
                return True
            else:
                logger.warning(f"⚠️ Ollama недоступен (status={response.status_code})")
                return False
        except Exception as e:
            logger.warning(f"⚠️  Ollama недоступен: {e}")
            logger.warning("💡 Запустите Ollama: ollama serve")
            return False
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> str:
        """
        Генерация текста через LLM
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт (опционально)
            temperature: Температура генерации (опционально)
            max_tokens: Максимальное количество токенов (опционально)
            timeout: Таймаут запроса в секундах (опционально, переопределяет значение по умолчанию)
        
        Returns:
            Сгенерированный текст
        """
        if self.provider == "ollama":
            return await self._generate_ollama(prompt, system_prompt, temperature, max_tokens, timeout)
        elif self.provider == "openai":
            return await self._generate_openai(prompt, system_prompt, temperature, max_tokens, timeout)
        elif self.provider == "gemini":
            return await self._generate_gemini(prompt, system_prompt, temperature, max_tokens, timeout)
        else:
            raise ValueError(f"Неизвестный провайдер: {self.provider}")
    
    async def _generate_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> str:
        """Генерация через Ollama"""
        # Используем переданный таймаут или значение по умолчанию
        request_timeout = timeout if timeout is not None else self.timeout
        try:
            # Пробуем сначала /api/chat (новый API)
            try:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature or self.temperature
                    }
                }
                
                if max_tokens:
                    payload["options"]["num_predict"] = max_tokens
                
                logger.debug(f"📤 Ollama запрос к /api/chat: model={self.model}, timeout={request_timeout}s")
                response = await self.client.post("/api/chat", json=payload, timeout=request_timeout)
                response.raise_for_status()
                
                result = response.json()
                content = result.get("message", {}).get("content", "")
                if content:
                    logger.debug(f"✅ Ollama ответ получен ({len(content)} символов)")
                    return content
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning(f"⚠️ /api/chat не поддерживается, пробуем /api/generate")
                    # Fallback на старый API /api/generate
                else:
                    raise
            
            # Fallback: используем старый API /api/generate
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": temperature or self.temperature
                }
            }
            
            if max_tokens:
                payload["options"]["num_predict"] = max_tokens
            
            logger.debug(f"📤 Ollama запрос к /api/generate: model={self.model}, timeout={request_timeout}s")
            response = await self.client.post("/api/generate", json=payload, timeout=request_timeout)
            response.raise_for_status()
            
            result = response.json()
            content = result.get("response", "")
            logger.debug(f"✅ Ollama ответ получен через /api/generate ({len(content)} символов)")
            return content
            
        except httpx.TimeoutException as e:
            logger.error(f"⏱️ Таймаут запроса к Ollama (timeout={request_timeout}s): {e}")
            raise ConnectionError(f"Ollama не ответил в течение {request_timeout} секунд. Модель {self.model} может быть слишком медленной или сервер перегружен.")
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP ошибка Ollama: {e.response.status_code} - {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка генерации через Ollama: {e}", exc_info=True)
            raise
    
    async def _generate_openai(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> str:
        """Генерация через OpenAI/ProxyAPI"""
        # Используем переданный таймаут или значение по умолчанию
        request_timeout = timeout if timeout is not None else self.timeout
        try:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            logger.debug(f"📤 OpenAI запрос: model={self.model}, timeout={request_timeout}s, prompt_len={len(prompt)}")
            
            # Передаем timeout в метод create() как в sql4A
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or 2000,  # Ограничиваем max_tokens для ускорения
                timeout=request_timeout  # Явно передаем timeout в запрос
            )
            
            content = response.choices[0].message.content
            logger.debug(f"✅ OpenAI ответ получен ({len(content)} символов)")
            return content
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации через OpenAI: {e}")
            raise
    
    async def _generate_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> str:
        """Генерация через Gemini/ProxyAPI через REST API"""
        # Используем переданный таймаут или значение по умолчанию
        request_timeout = timeout if timeout is not None else self.timeout
        try:
            # Формируем содержимое запроса
            parts = [{"text": prompt}]
            
            # Формируем запрос согласно документации ProxyAPI
            # https://api.proxyapi.ru/google/v1beta/models/{model}:generateContent
            request_data = {
                "contents": [{
                    "parts": parts
                }],
                "generationConfig": {
                    "temperature": temperature or self.temperature,
                    "maxOutputTokens": max_tokens or 8000,  # Увеличено для Gemini 3 Pro
                }
            }
            
            # Добавляем system instruction если есть
            if system_prompt:
                request_data["systemInstruction"] = {
                    "parts": [{"text": system_prompt}]
                }
            
            # Формируем URL для ProxyAPI
            # Формат модели: gemini-3-pro-preview -> models/gemini-3-pro-preview:generateContent
            model_endpoint = f"/v1beta/models/{self.model}:generateContent"
            
            logger.debug(f"📤 Gemini запрос к ProxyAPI: {self.base_url}{model_endpoint}, timeout={request_timeout}s")
            
            response = await self.client.post(
                model_endpoint,
                json=request_data,
                timeout=request_timeout
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Извлекаем текст из ответа
            # Формат ответа: {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
            candidates = result.get("candidates", [])
            if candidates:
                candidate = candidates[0]
                finish_reason = candidate.get("finishReason", "")
                
                # Проверяем причину завершения
                if finish_reason == "MAX_TOKENS":
                    logger.warning(f"⚠️ Gemini достиг лимита токенов (finishReason: {finish_reason})")
                elif finish_reason == "SAFETY":
                    logger.warning(f"⚠️ Gemini заблокировал ответ по соображениям безопасности (finishReason: {finish_reason})")
                    raise Exception(f"Gemini заблокировал ответ по соображениям безопасности. Попробуйте переформулировать запрос.")
                elif finish_reason == "RECITATION":
                    logger.warning(f"⚠️ Gemini заблокировал ответ из-за рецитации (finishReason: {finish_reason})")
                    raise Exception(f"Gemini заблокировал ответ из-за рецитации. Попробуйте переформулировать запрос.")
                
                content = candidate.get("content", {})
                
                # Проверяем, есть ли content и не пустой ли он
                if not content:
                    # Пустой content может означать, что Gemini использовал thinking tokens, но не сгенерировал текст
                    usage_metadata = result.get("usageMetadata", {})
                    thoughts_token_count = usage_metadata.get("thoughtsTokenCount", 0)
                    
                    if thoughts_token_count > 0:
                        logger.warning(f"⚠️ Gemini использовал thinking tokens ({thoughts_token_count}), но не вернул текст (finishReason: {finish_reason})")
                        raise Exception(
                            f"Gemini использовал thinking tokens, но не сгенерировал видимый текст. "
                            f"Возможно, модель решила, что ответ не требуется, или произошла ошибка. "
                            f"Попробуйте переформулировать запрос или использовать другую модель."
                        )
                    else:
                        logger.warning(f"⚠️ Gemini вернул пустой content (finishReason: {finish_reason})")
                        raise Exception(
                            f"Gemini вернул пустой ответ (finishReason: {finish_reason}). "
                            f"Попробуйте переформулировать запрос или увеличить maxOutputTokens."
                        )
                
                parts = content.get("parts", [])
                if parts:
                    text = parts[0].get("text", "")
                    if text:
                        logger.debug(f"✅ Gemini ответ получен ({len(text)} символов)")
                        return text
                    else:
                        logger.warning(f"⚠️ Gemini вернул пустой текст в parts (finishReason: {finish_reason})")
                        # Если текст пустой, но есть finishReason, возвращаем сообщение об ошибке
                        if finish_reason:
                            raise Exception(f"Gemini вернул пустой текст (finishReason: {finish_reason}). Попробуйте увеличить maxOutputTokens или переформулировать запрос.")
                else:
                    logger.warning(f"⚠️ Gemini не вернул parts в content (finishReason: {finish_reason}, content: {content})")
                    raise Exception(
                        f"Gemini не вернул parts в content (finishReason: {finish_reason}). "
                        f"Возможно, модель использовала thinking tokens без генерации текста. "
                        f"Попробуйте переформулировать запрос."
                    )
            
            # Если нет candidates или они пустые
            usage_metadata = result.get("usageMetadata", {})
            error_msg = f"Пустой ответ от Gemini. "
            if usage_metadata:
                error_msg += f"Использовано токенов: {usage_metadata.get('totalTokenCount', 0)}. "
            error_msg += f"Ответ: {result}"
            raise Exception(error_msg)
            
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP ошибка Gemini: {e.response.status_code if hasattr(e, 'response') else 'unknown'} - {e.response.text[:200] if hasattr(e, 'response') else str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка генерации через Gemini: {e}")
            raise
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Генерация JSON ответа
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт (опционально)
        
        Returns:
            Распарсенный JSON объект
        """
        import json
        
        # Добавляем инструкцию для JSON формата
        json_prompt = f"{prompt}\n\nВерни ответ ТОЛЬКО в формате JSON, без дополнительного текста."
        
        response = await self.generate(json_prompt, system_prompt)
        
        # Пытаемся извлечь JSON из ответа
        try:
            # Ищем JSON в ответе
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
            logger.error(f"Ответ: {response}")
            raise


# Singleton instance
_llm_client_instance: Optional[LLMClient] = None


def get_llm_client(provider: Optional[str] = None) -> LLMClient:
    """
    Получить экземпляр LLM клиента (singleton)
    
    Args:
        provider: Провайдер LLM. Если указан и отличается от текущего, синглтон будет переинициализирован
    """
    global _llm_client_instance
    
    # Если указан провайдер и он отличается от текущего, переинициализируем
    if provider and (_llm_client_instance is None or _llm_client_instance.provider != provider.lower()):
        _llm_client_instance = None
    
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient(provider=provider)
    
    return _llm_client_instance


def reset_llm_client():
    """Сбросить синглтон LLM клиента (для переинициализации с новыми настройками)"""
    global _llm_client_instance
    _llm_client_instance = None

