"""
Конфигурация логирования для проекта 3dtoday
"""

import os
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / "config.env")

# Настройки логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_DIR.mkdir(exist_ok=True)

# Формат логов
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DETAILED_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"


def setup_logger(name: str, log_file: str = None, level: str = None) -> logging.Logger:
    """
    Настройка логгера с записью в файл и консоль
    
    Args:
        name: Имя логгера
        log_file: Имя файла лога (опционально)
        level: Уровень логирования (опционально)
    
    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    
    # Уровень логирования
    log_level = getattr(logging, level or LOG_LEVEL, logging.INFO)
    logger.setLevel(log_level)
    
    # Удаляем существующие handlers (если есть)
    logger.handlers.clear()
    
    # Форматтер
    formatter = logging.Formatter(DETAILED_LOG_FORMAT)
    
    # Handler для консоли
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler для файла (если указан)
    if log_file:
        file_path = LOG_DIR / log_file
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Глобальные логгеры для разных компонентов
def get_parser_logger():
    """Логгер для парсеров"""
    return setup_logger("parser", "parser.log")


def get_llm_logger():
    """Логгер для LLM клиента"""
    return setup_logger("llm", "llm.log")


def get_api_logger():
    """Логгер для API"""
    return setup_logger("api", "api.log")


def get_librarian_logger():
    """Логгер для библиотекаря"""
    return setup_logger("librarian", "librarian.log")


def get_vector_db_logger():
    """Логгер для векторной БД"""
    return setup_logger("vector_db", "vector_db.log")

