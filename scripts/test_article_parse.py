#!/usr/bin/env python3
"""
Скрипт для тестирования парсинга статьи через GPT-4o и Gemini
"""

import sys
import json
import httpx
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_BASE_URL = "http://localhost:8000"
TEST_URL = "https://3dtoday.ru/blogs/news3dtoday/ucenye-dvfu-sozdayut-prodvinutye-medicinskie-simulyatory"

def test_provider(provider: str, model: str, timeout: int = 600):
    """Тестирование провайдера"""
    print(f"\n{'=' * 70}")
    print(f"🧪 Тестирование: {provider.upper()} ({model})")
    print(f"{'=' * 70}\n")
    
    try:
        with httpx.Client(timeout=float(timeout + 60)) as client:
            response = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse",
                json={
                    "source": TEST_URL,
                    "source_type": "auto",
                    "llm_provider": provider,
                    "model": model,
                    "timeout": timeout
                },
                timeout=float(timeout + 60)
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    parsed = data.get('parsed_document', {})
                    review = data.get('review', {})
                    
                    print(f"✅ УСПЕХ!\n")
                    print(f"📄 СТАТЬЯ:")
                    print(f"   Заголовок: {parsed.get('title', 'не указан')}")
                    print(f"   Раздел: {parsed.get('section', 'не указан')}")
                    print(f"   Тип: {parsed.get('content_type', 'не указан')}")
                    print(f"   URL: {parsed.get('url', 'не указан')}")
                    print(f"   Изображений: {len(parsed.get('images', []))}")
                    
                    print(f"\n📊 АНАЛИЗ БИБЛИОТЕКАРЯ:")
                    print(f"   Релевантность: {review.get('relevance_score', 'не указана')}")
                    print(f"   Качество: {review.get('quality_score', 'не указано')}")
                    print(f"   Решение: {review.get('decision', 'не указано')}")
                    print(f"   Причина: {review.get('reason', 'не указана')[:200]}")
                    
                    print(f"\n📝 ABSTRACT:")
                    abstract = review.get("abstract", "")
                    if abstract:
                        print(f"   {abstract[:400]}..." if len(abstract) > 400 else f"   {abstract}")
                    else:
                        print("   Не указан")
                    
                    print(f"\n🔍 ДЕТАЛИ:")
                    if review.get("problem"):
                        print(f"   Проблема: {review.get('problem')}")
                    if review.get("symptoms"):
                        print(f"   Симптомы: {', '.join(review.get('symptoms', []))}")
                    if review.get("solutions"):
                        print(f"   Решений: {len(review.get('solutions', []))}")
                    if review.get("printer_models"):
                        print(f"   Принтеры: {', '.join(review.get('printer_models', []))}")
                    if review.get("materials"):
                        print(f"   Материалы: {', '.join(review.get('materials', []))}")
                    
                    return True
                else:
                    print(f"❌ ОШИБКА: {data.get('detail', 'неизвестная ошибка')}")
                    return False
            else:
                error_detail = response.json().get('detail', response.text)
                print(f"❌ HTTP ОШИБКА {response.status_code}: {error_detail[:500]}")
                return False
                
    except httpx.TimeoutException:
        print(f"❌ ТАЙМАУТ: Запрос превысил {timeout} секунд")
        return False
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print(f"\n🚀 Тестирование парсинга статьи:")
    print(f"   URL: {TEST_URL}\n")
    
    results = {}
    
    # Тест GPT-4o
    print("⏳ Запуск теста GPT-4o (это может занять до 10 минут)...")
    results['gpt4o'] = test_provider("openai", "gpt-4o", timeout=600)
    
    # Тест Gemini
    print("\n⏳ Запуск теста Gemini (это может занять до 10 минут)...")
    results['gemini'] = test_provider("gemini", "gemini-3-pro-preview", timeout=600)
    
    # Итоги
    print(f"\n{'=' * 70}")
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print(f"{'=' * 70}")
    print(f"GPT-4o: {'✅ Успех' if results.get('gpt4o') else '❌ Ошибка'}")
    print(f"Gemini:  {'✅ Успех' if results.get('gemini') else '❌ Ошибка'}")
    print(f"{'=' * 70}\n")

