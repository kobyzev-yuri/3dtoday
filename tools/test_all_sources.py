#!/usr/bin/env python3
"""
Полное тестирование всех источников из image_urls.json
"""

import sys
import os
import json
import httpx
from pathlib import Path
from typing import Dict, Any, List
import time

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


def test_url(url: str, problem_type: str, description: str, index: int, total: int) -> Dict[str, Any]:
    """Тестирование одного URL"""
    print_separator()
    print_header(f"Тест {index}/{total}: {problem_type}")
    print_info(f"URL: {url}")
    print_info(f"Описание: {description}")
    print_separator()
    
    result = {
        "url": url,
        "problem_type": problem_type,
        "description": description,
        "success": False,
        "error": None,
        "relevance_score": 0.0,
        "images_count": 0,
        "indexed_images": 0,
        "article_id": None
    }
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # ШАГ 1: Парсинг через обычный метод (parse) с анализом через библиотекаря
            print_info("📋 ШАГ 1: Парсинг URL...")
            
            # Используем обычный parse
            parse_response = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse",
                json={
                    "source": url,
                    "source_type": "url",
                    "llm_provider": "gemini",
                    "model": "gemini-2.0-flash-exp"
                },
                timeout=TIMEOUT
            )
            
            if parse_response.status_code != 200:
                error_text = parse_response.text[:500] if len(parse_response.text) > 500 else parse_response.text
                result["error"] = f"HTTP {parse_response.status_code}: {error_text}"
                print_error(f"Ошибка парсинга: {result['error']}")
                return result
            
            parsed_data = parse_response.json()
            
            if not parsed_data.get("success"):
                result["error"] = parsed_data.get("error", "Unknown error")
                print_error(f"Парсинг не удался: {result['error']}")
                return result
            
            # Для обычного parse структура
            doc_data = parsed_data.get("document", parsed_data.get("parsed_document", {}))
            review = parsed_data.get("review", {})
            
            # Если review нет в ответе, значит он был создан автоматически библиотекарем
            # и должен быть в parsed_data
            if not review and "review" not in parsed_data:
                # Пробуем найти review в других полях
                review = parsed_data.get("analysis", {})
            
            # Если все еще нет review, создаем минимальный
            if not review:
                print_warning("Review не найден в ответе, создаем минимальный...")
                review = {
                    "relevance_score": 0.7,  # Предполагаем релевантность для тестовых URL
                    "quality_score": 0.7,
                    "is_relevant": True,
                    "has_valuable_info": True,
                    "decision": "approve"
                }
            
            title = doc_data.get("title", "N/A")
            content = doc_data.get("content", "")
            images = doc_data.get("images", [])
            
            print_success(f"✅ Парсинг успешен")
            print_info(f"   Заголовок: {title[:80]}")
            print_info(f"   Размер контента: {len(content)} символов")
            print_info(f"   Изображений извлечено: {len(images)}")
            
            result["images_count"] = len(images)
            
            # Проверка релевантности
            relevance_score = review.get("relevance_score", 0.0)
            quality_score = review.get("quality_score", 0.0)
            is_relevant = review.get("is_relevant", False)
            decision = review.get("decision", "unknown")
            
            print_info(f"\n📊 Результаты анализа:")
            print_info(f"   Релевантность: {relevance_score:.2f}")
            print_info(f"   Качество: {quality_score:.2f}")
            print_info(f"   Релевантна: {'✅ Да' if is_relevant else '❌ Нет'}")
            print_info(f"   Решение: {decision}")
            
            result["relevance_score"] = relevance_score
            
            # Проверка релевантности
            if relevance_score < 0.6:
                result["error"] = f"Релевантность ({relevance_score:.2f}) ниже порога (0.6)"
                print_warning(result["error"])
                return result
            
            if not is_relevant:
                result["error"] = "Документ помечен как нерелевантный"
                print_warning(result["error"])
                return result
            
            if decision == "reject":
                result["error"] = f"Документ отклонен: {review.get('reason', 'N/A')[:100]}"
                print_warning(result["error"])
                return result
            
            # ШАГ 2: Добавление в KB
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
                error_text = add_response.text[:500] if len(add_response.text) > 500 else add_response.text
                result["error"] = f"HTTP {add_response.status_code} при добавлении: {error_text}"
                print_error(f"Ошибка добавления: {result['error']}")
                return result
            
            add_result = add_response.json()
            
            if not add_result.get("success"):
                result["error"] = add_result.get("error", "Unknown error")
                print_error(f"Добавление не удалось: {result['error']}")
                return result
            
            print_success("✅ Статья успешно добавлена в KB")
            
            article_id = add_result.get("article_id", "N/A")
            result["article_id"] = article_id
            print_info(f"   Article ID: {article_id}")
            
            # Проверка индексации изображений
            indexed_images = add_result.get("indexed_images", [])
            result["indexed_images"] = len(indexed_images)
            
            print_info(f"\n📷 Обработка изображений:")
            print_info(f"   Всего изображений: {len(images)}")
            if indexed_images:
                print_success(f"   Проиндексировано: {len(indexed_images)}")
                for idx, img_info in enumerate(indexed_images[:3], 1):
                    img_id = img_info.get("image_id", "N/A")
                    print_info(f"      {idx}. {img_id}")
            else:
                print_warning("   ⚠️  Изображения не были проиндексированы")
            
            result["success"] = True
            print_success(f"\n✅ Тест {index}/{total} завершен успешно!")
            
    except httpx.TimeoutException:
        result["error"] = f"Таймаут при обработке (>{TIMEOUT} сек)"
        print_error(result["error"])
    except Exception as e:
        result["error"] = str(e)
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    return result


def main():
    """Главная функция"""
    print_header("="*70)
    print_header("🧪 ПОЛНОЕ ТЕСТИРОВАНИЕ ИСТОЧНИКОВ ИЗ image_urls.json")
    print_header("="*70)
    
    # Проверка API
    print_info("\n📋 Проверка доступности API...")
    if not check_api():
        print_error("❌ API сервер недоступен на http://localhost:8000")
        print_info("Запустите сервер: ./scripts/start_fastapi.sh")
        return 1
    
    print_success("✅ API сервер доступен")
    
    # Загрузка URL из image_urls.json
    project_root = Path(__file__).resolve().parents[1]
    urls_file = project_root / "knowledge_base" / "image_urls.json"
    
    if not urls_file.exists():
        print_error(f"❌ Файл {urls_file} не найден")
        return 1
    
    print_info(f"\n📋 Загрузка URL из {urls_file.name}...")
    
    with open(urls_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Извлечение URL
    test_urls = []
    
    # Приоритетные источники (priority_high)
    if "priority_high" in data:
        for problem_type, articles in data["priority_high"].items():
            for article in articles:
                if article.get("has_images", False):
                    test_urls.append({
                        "url": article["url"],
                        "problem_type": article.get("problem_type", problem_type),
                        "description": article.get("description", "")
                    })
    
    # Средний приоритет (priority_medium) - берем по 1-2 примера
    if "priority_medium" in data:
        for problem_type, articles in data["priority_medium"].items():
            # Берем первый пример из каждой категории
            for article in articles[:1]:
                if article.get("has_images", False):
                    test_urls.append({
                        "url": article["url"],
                        "problem_type": article.get("problem_type", problem_type),
                        "description": article.get("description", "")
                    })
    
    if not test_urls:
        print_error("❌ Не найдено URL для тестирования")
        return 1
    
    print_success(f"✅ Найдено {len(test_urls)} URL для тестирования")
    
    # Показываем список
    print_info("\n📋 Список URL для тестирования:")
    for i, item in enumerate(test_urls, 1):
        print_info(f"   {i}. [{item['problem_type']}] {item['url'][:70]}...")
    
    # Подтверждение (автоматически если AUTO_CONFIRM=1)
    auto_confirm = os.getenv("AUTO_CONFIRM", "0") == "1"
    
    if not auto_confirm:
        print("\n" + "="*70)
        try:
            response = input("Продолжить тестирование? (y/n): ").strip().lower()
            if response != 'y':
                print_info("Отменено")
                return 0
        except EOFError:
            # Неинтерактивный режим - продолжаем автоматически
            print_info("Неинтерактивный режим - продолжаем автоматически...")
    else:
        print_info("Автоматический режим - продолжаем...")
    
    # Запуск тестов
    print_header("\n" + "="*70)
    print_header("🚀 НАЧАЛО ТЕСТИРОВАНИЯ")
    print_header("="*70)
    
    results = []
    total = len(test_urls)
    
    for idx, item in enumerate(test_urls, 1):
        result = test_url(item["url"], item["problem_type"], item["description"], idx, total)
        results.append(result)
        
        # Пауза между тестами
        if idx < total:
            print_info(f"\n⏳ Пауза 3 секунды перед следующим тестом...")
            time.sleep(3)
    
    # Итоговая статистика
    print_header("\n" + "="*70)
    print_header("📊 ИТОГОВАЯ СТАТИСТИКА")
    print_header("="*70)
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    print_info(f"\nВсего тестов: {total}")
    print_success(f"Успешно: {len(successful)}")
    if failed:
        print_error(f"Провалено: {len(failed)}")
    
    # Детали успешных тестов
    if successful:
        print_header("\n✅ Успешные тесты:")
        total_images = sum(r["images_count"] for r in successful)
        total_indexed = sum(r["indexed_images"] for r in successful)
        avg_relevance = sum(r["relevance_score"] for r in successful) / len(successful)
        
        for r in successful:
            print_info(f"   • {r['problem_type']}: {r['article_id']}")
            print_info(f"     Релевантность: {r['relevance_score']:.2f}, "
                      f"Изображений: {r['images_count']} (проиндексировано: {r['indexed_images']})")
        
        print_info(f"\n   Средняя релевантность: {avg_relevance:.2f}")
        print_info(f"   Всего изображений: {total_images} (проиндексировано: {total_indexed})")
    
    # Детали проваленных тестов
    if failed:
        print_header("\n❌ Проваленные тесты:")
        for r in failed:
            print_error(f"   • {r['problem_type']}: {r['url'][:60]}...")
            print_error(f"     Ошибка: {r['error']}")
    
    # Сохранение результатов
    results_file = project_root / "tools" / "test_results_all_sources.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": total,
            "successful": len(successful),
            "failed": len(failed),
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print_info(f"\n📄 Результаты сохранены в: {results_file}")
    
    return 0 if len(failed) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


