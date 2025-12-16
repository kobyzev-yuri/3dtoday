#!/usr/bin/env python3
"""
Тестирование всех вариантов парсинга и анализа:
1. Ollama (упрощенный, для ограниченных ресурсов)
2. Gemini (для анализа изображений и создания абстрактов)
3. OpenAI (альтернативный вариант)
4. Проверка фильтрации нерелевантного контента
"""

import sys
import json
import httpx
from pathlib import Path
from typing import Dict, Any, Optional, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_BASE_URL = "http://localhost:8000"
TIMEOUT = 600


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg): print(f"{Colors.GREEN}✅ {msg}{Colors.END}")
def print_error(msg): print(f"{Colors.RED}❌ {msg}{Colors.END}")
def print_info(msg): print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")
def print_warning(msg): print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")
def print_phase(msg): print(f"\n{Colors.CYAN}{Colors.BOLD}📋 {msg}{Colors.END}\n")
def print_provider(msg): print(f"{Colors.MAGENTA}{Colors.BOLD}🔧 {msg}{Colors.END}")


def check_api():
    """Проверка доступности API"""
    try:
        resp = httpx.get(f"{API_BASE_URL}/health", timeout=10)
        if resp.status_code == 200:
            print_success("API сервер доступен")
            return True
        else:
            print_error(f"API вернул код {resp.status_code}")
            return False
    except Exception as e:
        print_error(f"API недоступен: {e}")
        print_info("Запустите: PYTHONPATH=. uvicorn backend.app.main:app --reload")
        return False


def test_ollama_parsing(url: str, should_add: bool = False) -> Dict[str, Any]:
    """
    Тест упрощенного парсинга через Ollama (для ограниченных ресурсов)
    
    Args:
        url: URL статьи
        should_add: Добавлять ли в KB
    """
    print_provider("Тест: Ollama (упрощенный парсинг)")
    print_info(f"URL: {url}")
    print_info("Ожидаем: упрощенный парсинг без глубокого анализа LLM")
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # Парсинг через обычный endpoint с Ollama
            resp = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse",
                json={
                    "source": url,
                    "source_type": "url",
                    "llm_provider": "ollama"
                }
            )
            
            if resp.status_code != 200:
                error = resp.json().get('detail', resp.text) if resp.headers.get('content-type', '').startswith('application/json') else resp.text
                print_error(f"Ошибка парсинга: HTTP {resp.status_code}")
                print_error(f"Детали: {error[:300]}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}
            
            result = resp.json()
            
            if not result.get("success"):
                print_error(f"Парсинг не удался: {result.get('error', 'Unknown')}")
                return {"success": False, "error": result.get("error")}
            
            parsed_doc = result.get("parsed_document", {})
            review = result.get("review", {})
            
            print_success("✅ Парсинг через Ollama успешен")
            print_info(f"   Заголовок: {parsed_doc.get('title', 'N/A')[:80]}")
            print_info(f"   Размер контента: {len(parsed_doc.get('content', ''))} символов")
            
            relevance_score = review.get("relevance_score", 0.0)
            is_relevant = review.get("is_relevant", False)
            
            print_info(f"   Релевантность: {relevance_score:.2f}")
            print_info(f"   Релевантна: {'✅ Да' if is_relevant else '❌ Нет'}")
            
            images = parsed_doc.get("images", [])
            if images:
                print_info(f"   Изображений найдено: {len(images)}")
                print_warning("   ⚠️  Для анализа изображений рекомендуется использовать Gemini")
            else:
                print_info("   Изображения не найдены")
            
            if should_add and is_relevant and relevance_score >= 0.6:
                # Добавление в KB
                add_resp = client.post(
                    f"{API_BASE_URL}/api/kb/articles/add_from_parse",
                    json={
                        "parsed_document": parsed_doc,
                        "review": review,
                        "admin_decision": "approve",
                        "relevance_threshold": 0.6
                    }
                )
                
                if add_resp.status_code == 200:
                    add_result = add_resp.json()
                    print_success(f"   ✅ Статья добавлена в KB: {add_result.get('article_id', 'N/A')}")
                else:
                    print_error(f"   ❌ Ошибка добавления: HTTP {add_resp.status_code}")
            
            return {
                "success": True,
                "provider": "ollama",
                "relevance_score": relevance_score,
                "is_relevant": is_relevant,
                "images_count": len(images)
            }
            
    except Exception as e:
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def test_gemini_with_images(url: str, should_add: bool = False) -> Dict[str, Any]:
    """
    Тест парсинга через Gemini с анализом изображений
    
    Args:
        url: URL статьи (желательно с изображениями)
        should_add: Добавлять ли в KB
    """
    print_provider("Тест: Gemini (с анализом изображений)")
    print_info(f"URL: {url}")
    print_info("Ожидаем: анализ изображений через Gemini Vision API и создание абстрактов")
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # Парсинг через LLM endpoint с Gemini
            resp = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse_with_llm",
                json={
                    "url": url,
                    "llm_provider": "gemini",
                    "model": "gemini-3-pro-preview"
                }
            )
            
            if resp.status_code != 200:
                error = resp.json().get('detail', resp.text) if resp.headers.get('content-type', '').startswith('application/json') else resp.text
                print_error(f"Ошибка парсинга: HTTP {resp.status_code}")
                print_error(f"Детали: {error[:300]}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}
            
            result = resp.json()
            
            if not result.get("success"):
                print_error(f"Парсинг не удался: {result.get('error', 'Unknown')}")
                return {"success": False, "error": result.get("error")}
            
            parsed_doc = result.get("parsed_document", {})
            review = result.get("review", {})
            
            print_success("✅ Парсинг через Gemini успешен")
            print_info(f"   Заголовок: {parsed_doc.get('title', 'N/A')[:80]}")
            print_info(f"   Размер контента: {len(parsed_doc.get('content', ''))} символов")
            
            relevance_score = review.get("relevance_score", 0.0)
            is_relevant = review.get("is_relevant", False)
            abstract = review.get("abstract", "")
            
            print_info(f"   Релевантность: {relevance_score:.2f}")
            print_info(f"   Релевантна: {'✅ Да' if is_relevant else '❌ Нет'}")
            
            if abstract:
                print_success(f"   ✅ Abstract создан: {abstract[:150]}...")
            else:
                print_warning("   ⚠️  Abstract не создан")
            
            # Проверка изображений
            images = parsed_doc.get("images", [])
            if images:
                print_success(f"   ✅ Изображений найдено: {len(images)}")
                
                # Проверяем анализ изображений
                image_analysis = review.get("summary", {}).get("visual_indicators", [])
                if image_analysis:
                    print_success(f"   ✅ Изображения проанализированы: {len(image_analysis)} релевантных")
                    print_info(f"   Релевантные изображения: {', '.join(image_analysis[:3])}")
                else:
                    print_warning("   ⚠️  Анализ изображений не выполнен или изображения не релевантны")
                
                # Проверяем, что абстракты изображений добавлены в review
                problems_shown = review.get("summary", {}).get("problems_shown", [])
                if problems_shown:
                    print_success(f"   ✅ Проблемы из изображений: {', '.join(problems_shown)}")
            else:
                print_info("   Изображения не найдены")
            
            if should_add and is_relevant and relevance_score >= 0.6:
                # Добавление в KB
                add_resp = client.post(
                    f"{API_BASE_URL}/api/kb/articles/add_from_parse",
                    json={
                        "parsed_document": parsed_doc,
                        "review": review,
                        "admin_decision": "approve",
                        "relevance_threshold": 0.6
                    }
                )
                
                if add_resp.status_code == 200:
                    add_result = add_resp.json()
                    print_success(f"   ✅ Статья добавлена в KB: {add_result.get('article_id', 'N/A')}")
                    print_info(f"   ✅ Абстракты изображений должны быть в KB")
                else:
                    print_error(f"   ❌ Ошибка добавления: HTTP {add_resp.status_code}")
            
            return {
                "success": True,
                "provider": "gemini",
                "relevance_score": relevance_score,
                "is_relevant": is_relevant,
                "images_count": len(images),
                "has_abstract": bool(abstract),
                "images_analyzed": len(image_analysis) if image_analysis else 0
            }
            
    except Exception as e:
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def test_openai_parsing(url: str, should_add: bool = False) -> Dict[str, Any]:
    """
    Тест парсинга через OpenAI (альтернативный вариант)
    
    Args:
        url: URL статьи
        should_add: Добавлять ли в KB
    """
    print_provider("Тест: OpenAI (альтернативный вариант)")
    print_info(f"URL: {url}")
    print_info("Ожидаем: парсинг через GPT-4o")
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse_with_llm",
                json={
                    "url": url,
                    "llm_provider": "openai",
                    "model": "gpt-4o"
                }
            )
            
            if resp.status_code != 200:
                error = resp.json().get('detail', resp.text) if resp.headers.get('content-type', '').startswith('application/json') else resp.text
                print_error(f"Ошибка парсинга: HTTP {resp.status_code}")
                print_error(f"Детали: {error[:300]}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}
            
            result = resp.json()
            
            if not result.get("success"):
                print_error(f"Парсинг не удался: {result.get('error', 'Unknown')}")
                return {"success": False, "error": result.get("error")}
            
            parsed_doc = result.get("parsed_document", {})
            review = result.get("review", {})
            
            print_success("✅ Парсинг через OpenAI успешен")
            print_info(f"   Заголовок: {parsed_doc.get('title', 'N/A')[:80]}")
            
            relevance_score = review.get("relevance_score", 0.0)
            is_relevant = review.get("is_relevant", False)
            
            print_info(f"   Релевантность: {relevance_score:.2f}")
            print_info(f"   Релевантна: {'✅ Да' if is_relevant else '❌ Нет'}")
            
            return {
                "success": True,
                "provider": "openai",
                "relevance_score": relevance_score,
                "is_relevant": is_relevant
            }
            
    except Exception as e:
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def test_relevance_filtering() -> Dict[str, Any]:
    """
    Тест фильтрации нерелевантного контента
    
    Проверяет, что нерелевантные статьи отклоняются и не замусоривают KB
    """
    print_provider("Тест: Фильтрация нерелевантного контента")
    print_info("Проверяем, что система корректно отклоняет нерелевантные статьи")
    
    # Нерелевантные примеры
    non_relevant_cases = [
        {
            "title": "Какую музыку Вы слушаете при моделировании?",
            "content": "Привет всем! Интересно, какую музыку вы слушаете во время работы над 3D-моделями?",
            "expected_relevance": "< 0.6"
        },
        {
            "title": "Какой ваш любимый цвет?",
            "content": "Просто интересно узнать, какой цвет нравится людям больше всего.",
            "expected_relevance": "< 0.6"
        }
    ]
    
    results = []
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            for i, case in enumerate(non_relevant_cases, 1):
                print_info(f"\n   Тест {i}: {case['title']}")
                
                resp = client.post(
                    f"{API_BASE_URL}/api/kb/articles/add",
                    json={
                        "title": case["title"],
                        "content": case["content"],
                        "url": f"https://3dtoday.ru/test/non-relevant-{i}",
                        "section": "Оффтоп"
                    }
                )
                
                if resp.status_code == 400:
                    error_detail = resp.json().get('detail', resp.text)
                    print_success(f"   ✅ Статья корректно отклонена")
                    print_info(f"   Причина: {error_detail[:150]}")
                    
                    if "релевант" in error_detail.lower() or "relevance" in error_detail.lower():
                        results.append({
                            "case": case["title"],
                            "rejected": True,
                            "reason": "relevance_check"
                        })
                    else:
                        results.append({
                            "case": case["title"],
                            "rejected": True,
                            "reason": "other"
                        })
                elif resp.status_code == 200:
                    print_error(f"   ❌ Статья НЕ была отклонена (должна была быть)")
                    results.append({
                        "case": case["title"],
                        "rejected": False,
                        "error": "Should have been rejected"
                    })
                else:
                    print_warning(f"   ⚠️  Неожиданный статус: HTTP {resp.status_code}")
                    results.append({
                        "case": case["title"],
                        "rejected": None,
                        "error": f"HTTP {resp.status_code}"
                    })
    
    except Exception as e:
        print_error(f"Ошибка теста фильтрации: {e}")
        return {"success": False, "error": str(e)}
    
    # Итоги
    rejected_count = sum(1 for r in results if r.get("rejected") is True)
    total_count = len(results)
    
    if rejected_count == total_count:
        print_success(f"\n✅ Все нерелевантные статьи корректно отклонены ({rejected_count}/{total_count})")
        return {"success": True, "rejected": rejected_count, "total": total_count}
    else:
        print_error(f"\n❌ Не все статьи отклонены ({rejected_count}/{total_count})")
        return {"success": False, "rejected": rejected_count, "total": total_count, "results": results}


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Тестирование всех вариантов парсинга")
    parser.add_argument("--url", type=str, help="URL для тестирования")
    parser.add_argument("--ollama", action="store_true", help="Тест Ollama")
    parser.add_argument("--gemini", action="store_true", help="Тест Gemini с изображениями")
    parser.add_argument("--openai", action="store_true", help="Тест OpenAI")
    parser.add_argument("--filtering", action="store_true", help="Тест фильтрации нерелевантного")
    parser.add_argument("--all", action="store_true", help="Все тесты")
    parser.add_argument("--add", action="store_true", help="Добавлять в KB")
    parser.add_argument("--skip-health", action="store_true", help="Пропустить проверку API")
    
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("=" * 70)
    print("🧪 Тестирование всех вариантов парсинга и анализа")
    print("=" * 70)
    print(f"{Colors.END}\n")
    
    # Проверка API
    if not args.skip_health:
        if not check_api():
            print_error("Не удалось подключиться к API. Завершение.")
            return 1
    
    # Дефолтный URL с изображениями
    default_url = "https://www.simplify3d.com/resources/print-quality-troubleshooting/stringing-or-oozing/"
    test_url = args.url or default_url
    
    results = {}
    
    # Тест фильтрации
    if args.filtering or args.all:
        results["filtering"] = test_relevance_filtering()
    
    # Тест Ollama
    if args.ollama or args.all:
        results["ollama"] = test_ollama_parsing(test_url, should_add=args.add)
    
    # Тест Gemini с изображениями
    if args.gemini or args.all:
        results["gemini"] = test_gemini_with_images(test_url, should_add=args.add)
    
    # Тест OpenAI
    if args.openai or args.all:
        results["openai"] = test_openai_parsing(test_url, should_add=args.add)
    
    # Если ничего не выбрано, запускаем Gemini (самый важный)
    if not any([args.ollama, args.gemini, args.openai, args.filtering, args.all]):
        print_info("Запуск теста Gemini (по умолчанию, самый важный для изображений)")
        results["gemini"] = test_gemini_with_images(test_url, should_add=args.add)
    
    # Итоги
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}📊 Итоги тестирования{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")
    
    for test_name, result in results.items():
        if result.get("success"):
            provider = result.get("provider", test_name)
            relevance = result.get("relevance_score", "N/A")
            print_success(f"{test_name.upper()} ({provider}): ПРОЙДЕН (relevance={relevance})")
        elif result.get("rejected"):
            print_success(f"{test_name.upper()}: ФИЛЬТРАЦИЯ РАБОТАЕТ")
        else:
            print_error(f"{test_name.upper()}: ПРОВАЛЕН - {result.get('error', 'Unknown')}")
    
    all_passed = all(r.get("success") or r.get("rejected") for r in results.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())


