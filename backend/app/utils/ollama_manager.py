"""
Утилита для управления Ollama сервером
"""

import subprocess
import time
import logging
import httpx
from typing import Optional
import os

logger = logging.getLogger(__name__)


class OllamaManager:
    """Менеджер для запуска и проверки Ollama"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.process: Optional[subprocess.Popen] = None
    
    def is_running(self) -> bool:
        """Проверка, запущен ли Ollama"""
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def start(self, wait: bool = True, timeout: int = 30) -> bool:
        """
        Запуск Ollama сервера
        
        Args:
            wait: Ждать ли запуска сервера
            timeout: Таймаут ожидания в секундах
        
        Returns:
            True если успешно запущен
        """
        if self.is_running():
            logger.info("✅ Ollama уже запущен")
            return True
        
        try:
            logger.info("🚀 Запуск Ollama сервера...")
            
            # Запуск в фоновом режиме
            self.process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            if wait:
                # Ждем запуска
                for i in range(timeout):
                    if self.is_running():
                        logger.info("✅ Ollama успешно запущен")
                        return True
                    time.sleep(1)
                
                logger.warning(f"⚠️  Ollama не запустился за {timeout} секунд")
                return False
            else:
                logger.info("✅ Команда запуска Ollama отправлена")
                return True
                
        except FileNotFoundError:
            logger.error("❌ Ollama не найден. Установите Ollama: https://ollama.ai")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Ollama: {e}")
            return False
    
    def stop(self):
        """Остановка Ollama сервера"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                logger.info("✅ Ollama остановлен")
            except:
                self.process.kill()
                logger.info("✅ Ollama принудительно остановлен")
            finally:
                self.process = None


def ensure_ollama_running(start_if_not: bool = True) -> bool:
    """
    Убедиться, что Ollama запущен
    
    Args:
        start_if_not: Запускать ли Ollama, если он не запущен
    
    Returns:
        True если Ollama доступен
    """
    manager = OllamaManager()
    
    if manager.is_running():
        return True
    
    if start_if_not:
        return manager.start()
    else:
        logger.warning("⚠️  Ollama не запущен. Запустите: ollama serve")
        return False

