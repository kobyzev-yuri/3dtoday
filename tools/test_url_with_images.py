#!/usr/bin/env python3
"""
Тест загрузки URL с изображениями и проверка их анализа
Аналогично тесту PDF, но для URL источников
"""

import sys
import json
import httpx
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_BASE_URL = "http://localhost:8000"
TIMEOUT = 600


def print_success(message: str):
    print(f"\033[92m✅ {message}\033[0m")


def print_error(message: str):
    print(f"\033[91m❌ {message}\033[0m")


def print_info(message: str):
    print(f"\033[94mℹ️  {message}\033[0m")


def print_warning(message: str):
    print(f"\033[93m⚠️  {message}\033[0m")


def test_url_with_images(url: str, provider: str = "gemini"):
    """
    Полный цикл тестирования URL с изображениями:
    1. Парсинг URL
    2. Проверка релевантности
    3. Добавление в KB (если релевантно)
    """
    print("\n" + "="*70)
    print(f"🧪 Тест: Добавление URL с изображениями в KB")
    print("="*70)
    
    print_info(f"URL: {url}")
    print_info(f"Провайдер: {provider}")
    
    # ШАГ 1: Парсинг URL
    print("\n📋 ШАГ 1: Парсинг URL")
    print_info("Отправка запроса на парсинг...")
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # Парсинг через LLM для лучшего извлечения изображений
            parse_response = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse_with_llm",
                json={
                    "url": url,
                    "provider": provider,
                    "model": "gemini-2.0-flash-exp" if provider == "gemini" else None
                },
                timeout=TIMEOUT
            )
            
            if parse_response.status_code != 200:
                print_error(f"Ошибка парсинга: HTTP {parse_response.status_code}")
                print_error(parse_response.text[:500])
                return False
            
            parsed_data = parse_response.json()
            
            if not parsed_data.get("success"):
                print_error(f"Парсинг не удался: {parsed_data.get('error', 'Unknown error')}")
                return False
            
            print_success("URL успешно распарсен")
            
            doc_data = parsed_data.get("document", {})
            title = doc_data.get("title", "N/A")
            content = doc_data.get("content", "")
            images = doc_data.get("images", [])
            
            print_info(f"Заголовок: {title}")
            print_info(f"Размер контента: {len(content)} символов")
            print_info(f"Изображений извлечено: {len(images)}")
            
            # Показываем информацию об изображениях
            if images:
                print_info("\n📷 Изображения:")
                for idx, img in enumerate(images[:5], 1):  # Показываем первые 5
                    img_url = img.get("url", "N/A")
                    img_title = img.get("title", img.get("alt", "N/A"))
                    print_info(f"  {idx}. {img_title[:50]} - {img_url[:80]}")
                if len(images) > 5:
                    print_info(f"  ... и еще {len(images) - 5} изображений")
            
            # Проверка релевантности
            review = parsed_data.get("review", {})
            if review:
                relevance_score = review.get("relevance_score", 0.0)
                quality_score = review.get("quality_score", 0.0)
                is_relevant = review.get("is_relevant", False)
                has_valuable_info = review.get("has_valuable_info", False)
                decision = review.get("decision", "unknown")
                reason = review.get("reason", "N/A")
                
                print_info(f"\n📊 Результаты анализа:")
                print_info(f"Релевантность: {relevance_score:.2f}")
                print_info(f"Качество: {quality_score:.2f}")
                print_info(f"Релевантна: {'✅ Да' if is_relevant else '❌ Нет'}")
                print_info(f"Есть ценная информация: {'✅ Да' if has_valuable_info else '❌ Нет'}")
                print_info(f"Решение: {decision}")
                print_info(f"Причина: {reason[:150] if reason else 'N/A'}")
                
                # Проверка релевантности
                if relevance_score < 0.6:
                    print_warning(f"Релевантность ({relevance_score:.2f}) ниже порога (0.6)")
                    print_info("Документ не будет добавлен в KB")
                    return False
                
                if not is_relevant:
                    print_warning("Документ помечен как нерелевантный")
                    print_info("Документ не будет добавлен в KB")
                    return False
                
                if decision == "reject":
                    print_warning(f"Документ отклонен: {reason[:100]}")
                    print_info("Документ не будет добавлен в KB")
                    return False
            
            # ШАГ 2: Добавление в KB
            print("\n📋 ШАГ 2: Добавление в KB")
            print_info("Отправка запроса на добавление...")
            
            add_response = client.post(
                f"{API_BASE_URL}/api/kb/articles/add_from_parse",
                json={
                    "document": doc_data,
                    "review": review
                },
                timeout=TIMEOUT
            )
            
            if add_response.status_code != 200:
                print_error(f"Ошибка добавления: HTTP {add_response.status_code}")
                print_error(add_response.text[:500])
                return False
            
            add_result = add_response.json()
            
            if not add_result.get("success"):
                print_error(f"Добавление не удалось: {add_result.get('error', 'Unknown error')}")
                return False
            
            print_success("Статья успешно добавлена в KB")
            
            article_id = add_result.get("article_id", "N/A")
            print_info(f"Article ID: {article_id}")
            
            # Проверка индексации изображений
            print("\n📷 Обработка изображений:")
            print_info(f"Всего изображений: {len(images)}")
            
            indexed_images = add_result.get("indexed_images", [])
            if indexed_images:
                print_success(f"Проиндексировано изображений: {len(indexed_images)}")
                for idx, img_info in enumerate(indexed_images[:5], 1):
                    img_id = img_info.get("image_id", "N/A")
                    img_abstract = img_info.get("abstract", "N/A")
                    print_info(f"  {idx}. ID: {img_id}")
                    if img_abstract and img_abstract != "N/A":
                        print_info(f"     Абстракт: {img_abstract[:100]}")
            else:
                print_warning("⚠️  Изображения не были проиндексированы (возможно, они будут обработаны позже)")
            
            return True
            
    except httpx.TimeoutException:
        print_error(f"Таймаут при обработке URL (>{TIMEOUT} сек)")
        return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Тест загрузки URL с изображениями")
    parser.add_argument("url", help="URL для тестирования")
    parser.add_argument("--provider", default="gemini", choices=["gemini", "openai", "ollama"],
                       help="LLM провайдер для парсинга")
    
    args = parser.parse_args()
    
    # Проверка доступности API
    try:
        with httpx.Client(timeout=10) as client:
            health_response = client.get(f"{API_BASE_URL}/health")
            if health_response.status_code != 200:
                print_error("API сервер недоступен")
                return 1
    except Exception as e:
        print_error(f"Не удалось подключиться к API: {e}")
        print_info("Убедитесь, что FastAPI сервер запущен на http://localhost:8000")
        return 1
    
    success = test_url_with_images(args.url, args.provider)
    
    if success:
        print("\n" + "="*70)
        print_success("✅ Тест завершен успешно!")
        print("="*70)
        return 0
    else:
        print("\n" + "="*70)
        print_error("❌ Тест завершен с ошибками")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())


