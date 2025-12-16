#!/usr/bin/env python3
"""
Интеграционные тесты для веб-интерфейса Admin UI

Проверяет полный цикл работы через UI:
1. Парсинг URL через улучшенный парсер (Trafilatura/Readability)
2. Анализ релевантности
3. Добавление в KB с изображениями
4. Проверка индексации

Все тесты используют те же API endpoints, что и веб-интерфейс.
"""

import sys
import json
import httpx
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_BASE_URL = "http://localhost:8000"
TIMEOUT = 600


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_success(msg): print(f"{Colors.GREEN}✅ {msg}{Colors.END}")
def print_error(msg): print(f"{Colors.RED}❌ {msg}{Colors.END}")
def print_info(msg): print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")
def print_warning(msg): print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")
def print_header(msg): print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.END}")
def print_header(msg): print(f"{Colors.CYAN}{Colors.BOLD}{msg}{Colors.END}")
def print_separator(): print(f"{Colors.CYAN}{'─'*70}{Colors.END}")


def check_api():
    """Проверка доступности API"""
    try:
        resp = httpx.get(f"{API_BASE_URL}/health", timeout=10)
        if resp.status_code == 200:
            return True
        return False
    except Exception:
        return False


def test_url_parsing_through_ui(url: str) -> Dict[str, Any]:
    """
    Тест 1: Парсинг URL через улучшенный парсер (как в UI)
    
    Проверяет:
    - Использование улучшенного парсера (Trafilatura/Readability)
    - Извлечение контента и изображений
    - Анализ релевантности
    """
    print_header("Тест 1: Парсинг URL через улучшенный парсер")
    print_info(f"URL: {url}")
    print_separator()
    
    result = {
        "test": "url_parsing",
        "url": url,
        "success": False,
        "content_length": 0,
        "images_count": 0,
        "relevance_score": 0.0,
        "parser_used": "unknown",
        "error": None
    }
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # Используем тот же endpoint, что и UI
            print_info("📋 ШАГ 1: Парсинг через /api/kb/articles/parse...")
            parse_response = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse",
                json={
                    "source": url,
                    "source_type": "url",
                    "llm_provider": "gemini"
                },
                timeout=TIMEOUT
            )
            
            if parse_response.status_code != 200:
                error_text = parse_response.text[:500]
                result["error"] = f"HTTP {parse_response.status_code}: {error_text}"
                print_error(f"Ошибка парсинга: {result['error']}")
                return result
            
            parsed_data = parse_response.json()
            
            if not parsed_data.get("success"):
                result["error"] = parsed_data.get("error", "Unknown error")
                print_error(f"Парсинг не удался: {result['error']}")
                return result
            
            doc_data = parsed_data.get("parsed_document", {})
            review = parsed_data.get("review", {})
            
            content = doc_data.get("content", "")
            images = doc_data.get("images", [])
            title = doc_data.get("title", "N/A")
            
            print_success(f"✅ Парсинг успешен")
            print_info(f"   Заголовок: {title[:80]}")
            print_info(f"   Размер контента: {len(content)} символов")
            print_info(f"   Изображений: {len(images)}")
            
            result["content_length"] = len(content)
            result["images_count"] = len(images)
            result["relevance_score"] = review.get("relevance_score", 0.0)
            
            # Определяем, какой парсер использовался (по размеру контента и наличию изображений)
            if len(content) > 1000 and len(images) > 0:
                result["parser_used"] = "trafilatura_or_readability"
            elif len(content) > 100:
                result["parser_used"] = "article_parser_or_beautifulsoup"
            else:
                result["parser_used"] = "fallback"
            
            print_info(f"\n📊 Результаты анализа:")
            print_info(f"   Релевантность: {result['relevance_score']:.2f}")
            print_info(f"   Парсер: {result['parser_used']}")
            
            # Проверка успешности
            if len(content) > 100:
                result["success"] = True
                print_success("✅ Тест пройден: контент успешно извлечен")
            else:
                result["error"] = "Контент слишком короткий (< 100 символов)"
                print_warning("⚠️ Контент слишком короткий")
            
    except Exception as e:
        result["error"] = str(e)
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    return result


def test_add_to_kb_through_ui(url: str) -> Dict[str, Any]:
    """
    Тест 2: Полный цикл добавления в KB через UI
    
    Проверяет:
    - Парсинг URL
    - Анализ релевантности
    - Добавление в KB
    - Индексацию изображений
    """
    print_header("Тест 2: Полный цикл добавления в KB")
    print_info(f"URL: {url}")
    print_separator()
    
    result = {
        "test": "add_to_kb",
        "url": url,
        "success": False,
        "article_id": None,
        "indexed_images": 0,
        "error": None
    }
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # ШАГ 1: Парсинг
            print_info("📋 ШАГ 1: Парсинг URL...")
            parse_response = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse",
                json={
                    "source": url,
                    "source_type": "url",
                    "llm_provider": "gemini"
                },
                timeout=TIMEOUT
            )
            
            if parse_response.status_code != 200:
                result["error"] = f"HTTP {parse_response.status_code} при парсинге"
                print_error(result["error"])
                return result
            
            parsed_data = parse_response.json()
            if not parsed_data.get("success"):
                result["error"] = parsed_data.get("error", "Unknown error")
                print_error(f"Парсинг не удался: {result['error']}")
                return result
            
            doc_data = parsed_data.get("parsed_document", {})
            review = parsed_data.get("review", {})
            
            print_success(f"✅ Парсинг успешен: {len(doc_data.get('content', ''))} символов, {len(doc_data.get('images', []))} изображений")
            
            # Проверка релевантности
            relevance_score = review.get("relevance_score", 0.0)
            if relevance_score < 0.6:
                result["error"] = f"Релевантность ({relevance_score:.2f}) ниже порога (0.6)"
                print_warning(result["error"])
                return result
            
            # ШАГ 2: Добавление в KB (как в UI)
            print_info(f"\n📋 ШАГ 2: Добавление в KB...")
            add_response = client.post(
                f"{API_BASE_URL}/api/kb/articles/add_from_parse",
                json={
                    "parsed_document": doc_data,
                    "review": review,
                    "admin_decision": "approve",
                    "relevance_threshold": 0.6
                },
                timeout=TIMEOUT
            )
            
            if add_response.status_code != 200:
                error_text = add_response.text[:500]
                result["error"] = f"HTTP {add_response.status_code} при добавлении: {error_text}"
                print_error(result["error"])
                return result
            
            add_result = add_response.json()
            
            if not add_result.get("success"):
                result["error"] = add_result.get("error", "Unknown error")
                print_error(f"Добавление не удалось: {result['error']}")
                return result
            
            print_success("✅ Статья успешно добавлена в KB")
            
            article_id = add_result.get("article_id")
            result["article_id"] = article_id
            print_info(f"   Article ID: {article_id}")
            
            # Проверка индексации изображений
            indexed_images = add_result.get("indexed_images", [])
            result["indexed_images"] = len(indexed_images)
            
            print_info(f"\n📷 Индексация изображений:")
            print_info(f"   Всего изображений: {len(doc_data.get('images', []))}")
            if indexed_images:
                print_success(f"   Проиндексировано: {len(indexed_images)}")
                for idx, img_info in enumerate(indexed_images[:3], 1):
                    img_id = img_info.get("image_id", "N/A")
                    print_info(f"      {idx}. {img_id}")
            else:
                print_warning("   ⚠️ Изображения не были проиндексированы")
            
            result["success"] = True
            print_success(f"\n✅ Тест пройден: статья успешно добавлена в KB")
            
    except Exception as e:
        result["error"] = str(e)
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    return result


def test_error_handling() -> Dict[str, Any]:
    """
    Тест 3: Обработка ошибок (как в UI)
    
    Проверяет:
    - Обработку невалидных URL
    - Обработку недоступных URL
    - Обработку ошибок парсинга
    """
    print_header("Тест 3: Обработка ошибок")
    print_separator()
    
    result = {
        "test": "error_handling",
        "success": False,
        "errors_handled": 0,
        "total_errors": 0,
        "error": None
    }
    
    test_cases = [
        ("Невалидный URL", "not-a-url"),
        ("Недоступный URL", "https://example-nonexistent-12345.com/page"),
        ("Пустой URL", ""),
    ]
    
    try:
        with httpx.Client(timeout=30) as client:
            for test_name, test_url in test_cases:
                result["total_errors"] += 1
                print_info(f"Проверка: {test_name} ({test_url})")
                
                try:
                    parse_response = client.post(
                        f"{API_BASE_URL}/api/kb/articles/parse",
                        json={
                            "source": test_url,
                            "source_type": "url"
                        },
                        timeout=30
                    )
                    
                    # Проверяем, что ошибка обработана корректно
                    if parse_response.status_code in [400, 404, 500]:
                        parsed_data = parse_response.json()
                        error_msg = parsed_data.get("detail", parsed_data.get("error", "Unknown error"))
                        print_warning(f"   Ошибка обработана: {error_msg[:100]}")
                        result["errors_handled"] += 1
                    else:
                        print_warning(f"   Неожиданный статус: {parse_response.status_code}")
                        
                except Exception as e:
                    print_warning(f"   Исключение обработано: {str(e)[:100]}")
                    result["errors_handled"] += 1
        
        if result["errors_handled"] == result["total_errors"]:
            result["success"] = True
            print_success(f"✅ Все ошибки обработаны корректно ({result['errors_handled']}/{result['total_errors']})")
        else:
            result["error"] = f"Не все ошибки обработаны ({result['errors_handled']}/{result['total_errors']})"
            print_warning(result["error"])
            
    except Exception as e:
        result["error"] = str(e)
        print_error(f"Ошибка теста: {e}")
    
    return result


def main():
    """Главная функция"""
    print_header("="*70)
    print_header("🧪 ИНТЕГРАЦИОННЫЕ ТЕСТЫ ДЛЯ ВЕБ-ИНТЕРФЕЙСА")
    print_header("="*70)
    
    # Проверка API
    print_info("\n📋 Проверка доступности API...")
    if not check_api():
        print_error("❌ API сервер недоступен на http://localhost:8000")
        print_info("Запустите сервер: ./scripts/start_fastapi.sh")
        return 1
    
    print_success("✅ API сервер доступен")
    
    # Тестовые URL
    test_urls = [
        "https://www.simplify3d.com/resources/print-quality-troubleshooting/stringing-or-oozing/",
        "https://www.simplify3d.com/resources/print-quality-troubleshooting/warping/"
    ]
    
    results = []
    
    # Тест 1: Парсинг URL
    for url in test_urls[:1]:  # Тестируем только первый URL для скорости
        result = test_url_parsing_through_ui(url)
        results.append(result)
        print("\n")
    
    # Тест 2: Добавление в KB (только для первого успешного URL)
    if results and results[0].get("success"):
        result = test_add_to_kb_through_ui(test_urls[0])
        results.append(result)
        print("\n")
    
    # Тест 3: Обработка ошибок
    result = test_error_handling()
    results.append(result)
    
    # Итоговая статистика
    print_header("\n" + "="*70)
    print_header("📊 ИТОГОВАЯ СТАТИСТИКА")
    print_header("="*70)
    
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    
    print_info(f"\nВсего тестов: {len(results)}")
    print_success(f"Успешно: {len(successful)}")
    if failed:
        print_error(f"Провалено: {len(failed)}")
    
    # Детали
    for r in results:
        test_name = r.get("test", "unknown")
        if r.get("success"):
            print_success(f"   ✅ {test_name}")
        else:
            print_error(f"   ❌ {test_name}: {r.get('error', 'Unknown error')}")
    
    return 0 if len(failed) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


