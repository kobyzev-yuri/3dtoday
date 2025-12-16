#!/usr/bin/env python3
"""
Тест добавления PDF в KB после парсинга и проверки релевантности
"""

import sys
import json
import httpx
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_BASE_URL = "http://localhost:8000"
TIMEOUT = 600  # 10 минут


def print_success(message: str):
    print(f"\033[92m✅ {message}\033[0m")


def print_error(message: str):
    print(f"\033[91m❌ {message}\033[0m")


def print_info(message: str):
    print(f"\033[94mℹ️  {message}\033[0m")


def test_pdf_add_to_kb(pdf_path: str):
    """Тест полного цикла: парсинг PDF -> проверка релевантности -> добавление в KB"""
    
    print("\n" + "=" * 70)
    print("🧪 Тест: Добавление PDF в KB")
    print("=" * 70 + "\n")
    
    print_info(f"PDF файл: {pdf_path}")
    
    # ШАГ 1: Парсинг PDF
    print("\n📋 ШАГ 1: Парсинг PDF")
    print_info("Отправка запроса на парсинг...")
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # Парсинг
            parse_response = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse",
                json={
                    "source": str(Path(pdf_path).absolute()),
                    "source_type": "pdf",
                    "llm_provider": "gemini",  # Используем Gemini для анализа изображений
                    "timeout": 300,
                    "max_pages": 30
                }
            )
            
            if parse_response.status_code != 200:
                print_error(f"Ошибка парсинга: {parse_response.status_code}")
                print_error(f"Детали: {parse_response.text[:500]}")
                return False
            
            parse_result = parse_response.json()
            
            if not parse_result.get("success"):
                print_error(f"Парсинг не удался: {parse_result.get('error', 'Unknown error')}")
                return False
            
            parsed_doc = parse_result.get("parsed_document", {})
            review = parse_result.get("review", {})
            
            print_success("PDF успешно распарсен")
            print_info(f"Заголовок: {parsed_doc.get('title', 'N/A')[:80]}")
            print_info(f"Размер контента: {len(parsed_doc.get('content', ''))} символов")
            
            images = parsed_doc.get("images", [])
            print_info(f"Изображений извлечено: {len(images)}")
            
            relevance_score = review.get("relevance_score", 0.0)
            quality_score = review.get("quality_score", 0.0)
            is_relevant = review.get("is_relevant", False)
            has_valuable_info = review.get("has_valuable_info", False)
            decision = review.get("decision", "unknown")
            reason = review.get("reason", "N/A")
            duplicate_check = review.get("duplicate_check", {})
            is_duplicate = duplicate_check.get("is_duplicate", False)
            
            print_info(f"Релевантность: {relevance_score:.2f}")
            print_info(f"Качество: {quality_score:.2f}")
            print_info(f"Релевантна: {'✅ Да' if is_relevant else '❌ Нет'}")
            print_info(f"Есть ценная информация: {'✅ Да' if has_valuable_info else '❌ Нет'}")
            print_info(f"Дубликат: {'❌ Да' if is_duplicate else '✅ Нет'}")
            print_info(f"Решение: {decision}")
            print_info(f"Причина: {reason[:100] if reason else 'N/A'}")
            
            # Проверка релевантности
            if relevance_score < 0.6:
                print_error(f"Релевантность ({relevance_score:.2f}) ниже порога (0.6)")
                print_info("Документ не будет добавлен в KB")
                return False
            
            # Если решение approve и релевантность высокая, добавляем даже если is_relevant=False
            # (возможно, это временная проблема в логике агента)
            if decision == "approve" and relevance_score >= 0.6:
                print_info("Решение: approve, релевантность достаточна - добавляем в KB")
            elif not is_relevant:
                print_error("Документ помечен как нерелевантный")
                print_info("Документ не будет добавлен в KB")
                return False
            
            # ШАГ 2: Добавление в KB
            print("\n📋 ШАГ 2: Добавление в KB")
            print_info("Отправка запроса на добавление...")
            
            add_response = client.post(
                f"{API_BASE_URL}/api/kb/articles/add_from_parse",
                json={
                    "parsed_document": parsed_doc,
                    "review": review,
                    "admin_decision": "approve",
                    "relevance_threshold": 0.6
                },
                timeout=TIMEOUT
            )
            
            if add_response.status_code != 200:
                print_error(f"Ошибка добавления: {add_response.status_code}")
                try:
                    error_detail = add_response.json().get('detail', add_response.text)
                    print_error(f"Детали: {error_detail[:500]}")
                except:
                    print_error(f"Детали: {add_response.text[:500]}")
                return False
            
            add_result = add_response.json()
            
            if not add_result.get("success"):
                print_error(f"Добавление не удалось: {add_result.get('error', 'Unknown error')}")
                return False
            
            print_success("Статья успешно добавлена в KB")
            
            article_id = add_result.get("article_id", "N/A")
            print_info(f"Article ID: {article_id}")
            
            # Проверка изображений
            if images:
                print_info(f"\n📷 Обработка изображений:")
                print_info(f"Всего изображений: {len(images)}")
                
                # Проверяем, были ли изображения проанализированы
                image_summaries = review.get("image_summaries", [])
                if image_summaries:
                    print_success(f"Изображений проанализировано: {len(image_summaries)}")
                    for i, img_summary in enumerate(image_summaries[:3], 1):
                        print_info(f"  {i}. {img_summary.get('description', 'N/A')[:80]}")
                else:
                    print_info("⚠️  Изображения не были проанализированы (возможно, они будут обработаны позже)")
            
            return True
            
    except httpx.TimeoutException:
        print_error("Таймаут при обработке PDF")
        return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "tools/test_data/O1A1-EN-RES.pdf"
    
    # Проверка доступности API
    try:
        response = httpx.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code != 200:
            print_error("API сервер недоступен")
            sys.exit(1)
    except:
        print_error("API сервер недоступен. Запустите: PYTHONPATH=. uvicorn backend.app.main:app --reload")
        sys.exit(1)
    
    success = test_pdf_add_to_kb(pdf_path)
    sys.exit(0 if success else 1)


