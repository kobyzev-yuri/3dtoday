#!/usr/bin/env python3
"""
Полное тестирование всех трех фаз добавления статей в KB:
1. Парсинг (извлечение контента)
2. Анализ релевантности (проверка через библиотекаря)
3. Размещение в KB (индексация)

Также тестирует отклонение нерелевантных статей.
"""

import sys
import json
import httpx
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
    END = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg): print(f"{Colors.GREEN}✅ {msg}{Colors.END}")
def print_error(msg): print(f"{Colors.RED}❌ {msg}{Colors.END}")
def print_info(msg): print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")
def print_warning(msg): print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")
def print_phase(msg): print(f"\n{Colors.CYAN}{Colors.BOLD}📋 {msg}{Colors.END}\n")


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


def test_full_workflow_relevant(
    url: str,
    method: str = "llm",
    provider: str = "gemini",
    should_add: bool = True
) -> Dict[str, Any]:
    """
    Полный тест всех трех фаз для релевантной статьи
    
    Args:
        url: URL статьи
        method: "llm" или "normal"
        provider: "gemini" или "openai"
        should_add: Добавлять ли в KB (True) или только тестировать парсинг (False)
    """
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}🧪 Полный тест: Релевантная статья{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")
    print_info(f"URL: {url}")
    print_info(f"Метод: {method.upper()}")
    print_info(f"Провайдер: {provider}")
    
    results = {
        "phase1_parsing": None,
        "phase2_relevance": None,
        "phase3_indexing": None
    }
    
    # ============================================
    # ФАЗА 1: ПАРСИНГ
    # ============================================
    print_phase("ФАЗА 1: ПАРСИНГ")
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            if method == "llm":
                resp = client.post(
                    f"{API_BASE_URL}/api/kb/articles/parse_with_llm",
                    json={
                        "url": url,
                        "llm_provider": provider,
                        "model": "gemini-3-pro-preview" if provider == "gemini" else "gpt-4o"
                    }
                )
            else:
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
                return {"success": False, "error": f"HTTP {resp.status_code}", "results": results}
            
            parse_result = resp.json()
            
            if not parse_result.get("success"):
                print_error(f"Парсинг не удался: {parse_result.get('error', 'Unknown')}")
                return {"success": False, "error": parse_result.get("error"), "results": results}
            
            parsed_doc = parse_result.get("parsed_document", {})
            review = parse_result.get("review", {})
            
            print_success("✅ ФАЗА 1: Парсинг успешен")
            print_info(f"   Заголовок: {parsed_doc.get('title', 'N/A')[:80]}")
            print_info(f"   Размер контента: {len(parsed_doc.get('content', ''))} символов")
            
            images = parsed_doc.get("images", [])
            if images:
                print_success(f"   Изображений извлечено: {len(images)}")
            else:
                print_info("   Изображения не найдены")
            
            results["phase1_parsing"] = {
                "success": True,
                "parsed_document": parsed_doc,
                "review": review
            }
            
    except Exception as e:
        print_error(f"Ошибка фазы 1: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e), "results": results}
    
    # ============================================
    # ФАЗА 2: АНАЛИЗ РЕЛЕВАНТНОСТИ
    # ============================================
    print_phase("ФАЗА 2: АНАЛИЗ РЕЛЕВАНТНОСТИ")
    
    relevance_score = review.get("relevance_score", 0.0)
    quality_score = review.get("quality_score", 0.0)
    is_relevant = review.get("is_relevant", False)
    decision = review.get("decision", "needs_review")
    
    print_info(f"   Релевантность: {relevance_score:.2f}")
    print_info(f"   Качество: {quality_score:.2f}")
    print_info(f"   Релевантна: {'✅ Да' if is_relevant else '❌ Нет'}")
    print_info(f"   Решение библиотекаря: {decision}")
    
    # Проверка порогов
    if relevance_score >= 0.7:
        print_success(f"   ✅ Релевантность >= 0.7 (одобрено)")
    elif relevance_score >= 0.6:
        print_warning(f"   ⚠️  Релевантность 0.6-0.7 (требуется проверка)")
    else:
        print_error(f"   ❌ Релевантность < 0.6 (отклонено)")
    
    if not is_relevant:
        print_error("   ❌ Статья помечена как нерелевантная")
        print_warning("   Тест завершен: статья не должна быть добавлена в KB")
        results["phase2_relevance"] = {
            "success": False,
            "relevance_score": relevance_score,
            "is_relevant": False,
            "decision": decision,
            "should_reject": True
        }
        return {"success": False, "error": "Статья не релевантна", "results": results}
    
    print_success("✅ ФАЗА 2: Статья релевантна")
    
    results["phase2_relevance"] = {
        "success": True,
        "relevance_score": relevance_score,
        "quality_score": quality_score,
        "is_relevant": is_relevant,
        "decision": decision
    }
    
    # ============================================
    # ФАЗА 3: РАЗМЕЩЕНИЕ В KB
    # ============================================
    if not should_add:
        print_warning("   Пропуск фазы 3: should_add=False")
        results["phase3_indexing"] = {"skipped": True}
        return {"success": True, "results": results}
    
    print_phase("ФАЗА 3: РАЗМЕЩЕНИЕ В KB")
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(
                f"{API_BASE_URL}/api/kb/articles/add_from_parse",
                json={
                    "parsed_document": parsed_doc,
                    "review": review,
                    "admin_decision": "approve",
                    "relevance_threshold": 0.6
                }
            )
            
            if resp.status_code != 200:
                error = resp.json().get('detail', resp.text) if resp.headers.get('content-type', '').startswith('application/json') else resp.text
                print_error(f"Ошибка добавления в KB: HTTP {resp.status_code}")
                print_error(f"Детали: {error[:300]}")
                results["phase3_indexing"] = {
                    "success": False,
                    "error": f"HTTP {resp.status_code}"
                }
                return {"success": False, "error": f"HTTP {resp.status_code}", "results": results}
            
            add_result = resp.json()
            
            if add_result.get("success"):
                print_success("✅ ФАЗА 3: Статья успешно добавлена в KB")
                print_info(f"   Article ID: {add_result.get('article_id', 'N/A')}")
                print_info(f"   Релевантность: {add_result.get('relevance_score', 'N/A')}")
                
                results["phase3_indexing"] = {
                    "success": True,
                    "article_id": add_result.get("article_id"),
                    "relevance_score": add_result.get("relevance_score")
                }
            else:
                print_error(f"Добавление не удалось: {add_result.get('error', 'Unknown')}")
                results["phase3_indexing"] = {
                    "success": False,
                    "error": add_result.get("error")
                }
                return {"success": False, "error": add_result.get("error"), "results": results}
            
    except Exception as e:
        print_error(f"Ошибка фазы 3: {e}")
        import traceback
        traceback.print_exc()
        results["phase3_indexing"] = {"success": False, "error": str(e)}
        return {"success": False, "error": str(e), "results": results}
    
    print_success("\n✅ ВСЕ ТРИ ФАЗЫ УСПЕШНО ЗАВЕРШЕНЫ")
    return {"success": True, "results": results}


def test_rejection_non_relevant() -> Dict[str, Any]:
    """
    Тест отклонения нерелевантной статьи
    
    Использует пример нерелевантного контента (о музыке)
    """
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}🧪 Тест отклонения: Нерелевантная статья{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")
    
    # Нерелевантный контент (о музыке, не о 3D-печати)
    non_relevant_content = {
        "title": "Какую музыку Вы слушаете при моделировании?",
        "content": """
        Привет всем! Интересно, какую музыку вы слушаете во время работы над 3D-моделями?
        
        Я лично предпочитаю классическую музыку или джаз. Это помогает мне сосредоточиться.
        
        А вы что слушаете? Может быть рок или электронную музыку?
        
        Поделитесь своими предпочтениями!
        """,
        "url": "https://3dtoday.ru/blogs/offtopic/music-preferences",
        "section": "Оффтоп"
    }
    
    print_info(f"Заголовок: {non_relevant_content['title']}")
    print_info("Ожидаем: relevance_score < 0.6, is_relevant = False")
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # Тест через ручной ввод (валидация релевантности)
            resp = client.post(
                f"{API_BASE_URL}/api/kb/articles/add",
                json={
                    "title": non_relevant_content["title"],
                    "content": non_relevant_content["content"],
                    "url": non_relevant_content["url"],
                    "section": non_relevant_content["section"]
                }
            )
            
            # Ожидаем ошибку 400 (не релевантна)
            if resp.status_code == 400:
                error_detail = resp.json().get('detail', resp.text)
                print_success("✅ Статья корректно отклонена (HTTP 400)")
                print_info(f"   Причина: {error_detail[:200]}")
                
                # Проверяем, что в ошибке упоминается релевантность
                if "релевант" in error_detail.lower() or "relevance" in error_detail.lower():
                    print_success("   ✅ Ошибка содержит информацию о релевантности")
                    return {"success": True, "rejected": True, "reason": error_detail}
                else:
                    print_warning("   ⚠️  Ошибка не содержит явного упоминания релевантности")
                    return {"success": True, "rejected": True, "reason": error_detail}
            elif resp.status_code == 200:
                result = resp.json()
                print_error("❌ Статья НЕ была отклонена (должна была быть)")
                print_warning(f"   Статья была добавлена: {result.get('article_id', 'N/A')}")
                return {"success": False, "rejected": False, "error": "Статья не была отклонена"}
            else:
                print_error(f"❌ Неожиданный статус: HTTP {resp.status_code}")
                error_detail = resp.json().get('detail', resp.text) if resp.headers.get('content-type', '').startswith('application/json') else resp.text
                return {"success": False, "rejected": False, "error": f"HTTP {resp.status_code}: {error_detail[:200]}"}
                
    except Exception as e:
        print_error(f"Ошибка теста отклонения: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def test_manual_input_full_workflow() -> Dict[str, Any]:
    """
    Тест полного цикла через ручной ввод (JSON)
    """
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}🧪 Тест: Ручной ввод (полный цикл){Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")
    
    json_path = Path(__file__).parent / "test_data" / "sample_article.json"
    if not json_path.exists():
        print_error(f"Файл не найден: {json_path}")
        return {"success": False, "error": "File not found"}
    
    with open(json_path, "r", encoding="utf-8") as f:
        article_data = json.load(f)
    
    print_info(f"Заголовок: {article_data.get('title', 'N/A')}")
    
    # ФАЗА 1: Валидация (встроена в /api/kb/articles/add)
    print_phase("ФАЗА 1-2: Валидация и проверка релевантности")
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(
                f"{API_BASE_URL}/api/kb/articles/add",
                json={
                    "title": article_data.get("title"),
                    "content": article_data.get("content"),
                    "url": article_data.get("url", ""),
                    "section": article_data.get("section", "Техничка")
                }
            )
            
            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    print_success("✅ Статья успешно добавлена в KB")
                    print_info(f"   Article ID: {result.get('article_id', 'N/A')}")
                    
                    validation = result.get("validation", {})
                    relevance_score = validation.get("relevance_score", 0.0)
                    is_relevant = validation.get("is_relevant", False)
                    
                    print_info(f"   Релевантность: {relevance_score:.2f}")
                    print_info(f"   Релевантна: {'✅ Да' if is_relevant else '❌ Нет'}")
                    
                    return {
                        "success": True,
                        "article_id": result.get("article_id"),
                        "relevance_score": relevance_score,
                        "is_relevant": is_relevant
                    }
                else:
                    print_error(f"Добавление не удалось: {result.get('error', 'Unknown')}")
                    return {"success": False, "error": result.get("error")}
            elif resp.status_code == 400:
                error_detail = resp.json().get('detail', resp.text)
                print_error(f"Статья отклонена: {error_detail[:200]}")
                return {"success": False, "rejected": True, "reason": error_detail}
            else:
                error_detail = resp.json().get('detail', resp.text) if resp.headers.get('content-type', '').startswith('application/json') else resp.text
                print_error(f"HTTP {resp.status_code}: {error_detail[:200]}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}
                
    except Exception as e:
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Тестирование всех трех фаз добавления статей")
    parser.add_argument("--url", type=str, help="URL для тестирования")
    parser.add_argument("--method", choices=["llm", "normal"], default="llm", help="Метод парсинга")
    parser.add_argument("--provider", choices=["gemini", "openai"], default="gemini", help="LLM провайдер")
    parser.add_argument("--skip-add", action="store_true", help="Не добавлять в KB (только парсинг)")
    parser.add_argument("--rejection-only", action="store_true", help="Только тест отклонения")
    parser.add_argument("--manual-only", action="store_true", help="Только тест ручного ввода")
    parser.add_argument("--skip-health", action="store_true", help="Пропустить проверку API")
    
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("=" * 70)
    print("🧪 Тестирование всех трех фаз добавления статей в KB")
    print("=" * 70)
    print(f"{Colors.END}\n")
    
    # Проверка API
    if not args.skip_health:
        if not check_api():
            print_error("Не удалось подключиться к API. Завершение.")
            return 1
    
    results = {}
    
    # Тест отклонения нерелевантной статьи
    if args.rejection_only or not (args.url or args.manual_only):
        results["rejection"] = test_rejection_non_relevant()
    
    # Тест ручного ввода
    if args.manual_only or not (args.url or args.rejection_only):
        results["manual"] = test_manual_input_full_workflow()
    
    # Тест полного цикла через URL
    if args.url and not args.rejection_only and not args.manual_only:
        results["full_workflow"] = test_full_workflow_relevant(
            url=args.url,
            method=args.method,
            provider=args.provider,
            should_add=not args.skip_add
        )
    elif not args.rejection_only and not args.manual_only:
        # Используем дефолтный URL
        default_url = "https://www.simplify3d.com/resources/print-quality-troubleshooting/stringing-or-oozing/"
        results["full_workflow"] = test_full_workflow_relevant(
            url=default_url,
            method=args.method,
            provider=args.provider,
            should_add=not args.skip_add
        )
    
    # Итоги
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}📊 Итоги тестирования{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")
    
    for test_name, result in results.items():
        if result.get("success"):
            print_success(f"{test_name.upper()}: ПРОЙДЕН")
        elif result.get("rejected"):
            print_success(f"{test_name.upper()}: ОТКЛОНЕНИЕ РАБОТАЕТ КОРРЕКТНО")
        else:
            print_error(f"{test_name.upper()}: ПРОВАЛЕН - {result.get('error', 'Unknown')}")
    
    all_passed = all(r.get("success") or r.get("rejected") for r in results.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())


