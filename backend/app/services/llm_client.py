"""
Универсальный клиент для LLM (Ollama и ProxyAPI/OpenAI)
"""

import os
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / "config.env")

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Универсальный клиент для работы с LLM (Ollama или ProxyAPI/OpenAI)
    """
    
    def __init__(self):
        """Инициализация клиента на основе конфигурации"""
        self.provider = os.getenv("LLM_PROVIDER", "ollama").lower()
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Инициализация клиента в зависимости от провайдера"""
        if self.provider == "ollama":
            self._init_ollama()
        elif self.provider == "openai":
            self._init_openai()
        else:
            raise ValueError(f"Неизвестный провайдер LLM: {self.provider}")
    
    def _init_ollama(self):
        """Инициализация Ollama клиента"""
        try:
            import httpx
            
            self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            self.model = os.getenv("OLLAMA_MODEL", "llama3.1:70b")
            self.temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
            self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "500"))
            
            # Проверка доступности Ollama
            self._check_ollama_available()
            
            self.client = httpx.AsyncClient(
                base_url=self.ollama_url,
                timeout=self.timeout
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
            self.timeout = int(os.getenv("OPENAI_TIMEOUT", "60"))
            
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
    
    def _check_ollama_available(self):
        """Проверка доступности Ollama сервера"""
        import httpx
        
        try:
            response = httpx.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Ollama сервер доступен")
            else:
                raise ConnectionError(f"Ollama недоступен (status={response.status_code})")
        except Exception as e:
            logger.warning(f"⚠️  Ollama недоступен: {e}")
            logger.warning("💡 Запустите Ollama: ollama serve")
            raise
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Генерация текста через LLM
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт (опционально)
            temperature: Температура генерации (опционально)
            max_tokens: Максимальное количество токенов (опционально)
        
        Returns:
            Сгенерированный текст
        """
        if self.provider == "ollama":
            return await self._generate_ollama(prompt, system_prompt, temperature, max_tokens)
        else:
            return await self._generate_openai(prompt, system_prompt, temperature, max_tokens)
    
    async def _generate_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Генерация через Ollama"""
        try:
            # Формируем сообщения для /api/chat
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
            
            # Ollama использует /api/chat для чат-запросов
            response = await self.client.post("/api/chat", json=payload)
            response.raise_for_status()
            
            result = response.json()
            # Ollama возвращает {"message": {"role": "assistant", "content": "..."}}
            return result.get("message", {}).get("content", "")
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации через Ollama: {e}")
            raise
    
    async def _generate_openai(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Генерация через OpenAI/ProxyAPI"""
        try:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации через OpenAI: {e}")
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


def get_llm_client() -> LLMClient:
    """Получить экземпляр LLM клиента (singleton)"""
    global _llm_client_instance
    
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    
    return _llm_client_instance

