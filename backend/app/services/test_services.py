#!/usr/bin/env python3
"""
Тест базовых сервисов - проверка подключений
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.llm_client import get_llm_client
from services.vector_db import get_vector_db


async def test_llm_client():
    """Тест LLM клиента"""
    print("\n🔍 Тестирование LLM клиента...")
    
    try:
        llm = get_llm_client()
        print(f"  ✅ Клиент инициализирован (provider={llm.provider})")
        
        # Простой тест генерации
        response = await llm.generate(
            prompt="Скажи 'Привет' одним словом",
            system_prompt="Ты помощник. Отвечай кратко."
        )
        
        print(f"  ✅ Генерация работает: {response[:50]}...")
        return True
        
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False


async def test_vector_db():
    """Тест Vector DB клиента"""
    print("\n🔍 Тестирование Vector DB клиента...")
    
    try:
        db = get_vector_db()
        print(f"  ✅ Клиент инициализирован (type={db.db_type}, collection={db.collection_name})")
        
        # Получение статистики
        stats = db.get_statistics()
        print(f"  ✅ Статистика: {stats}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False


async def main():
    """Главная функция тестирования"""
    print("="*50)
    print("Тестирование базовых сервисов")
    print("="*50)
    
    results = {
        "llm": await test_llm_client(),
        "vector_db": await test_vector_db()
    }
    
    print("\n" + "="*50)
    print("Результаты тестирования:")
    print("="*50)
    
    for service, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {service}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✅ Все тесты пройдены!")
        return 0
    else:
        print("\n❌ Некоторые тесты не пройдены")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

