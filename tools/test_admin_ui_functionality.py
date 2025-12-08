#!/usr/bin/env python3
"""
Тесты функционала веб-интерфейса администрирования KB

Проверяет:
1. Загрузку JSON формата
2. Загрузку PDF формата с картинками
3. Загрузку URL

Все тесты используют те же API endpoints и библиотеки, что и веб-интерфейс.
"""

import sys
import json
import httpx
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from io import BytesIO

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_BASE_URL = "http://localhost:8000"
TIMEOUT = 600  # 10 минут для полного цикла парсинга и анализа


class Colors:
    """Цвета для вывода в консоль"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_success(message: str):
    """Вывод успешного сообщения"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")


def print_error(message: str):
    """Вывод сообщения об ошибке"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")


def print_info(message: str):
    """Вывод информационного сообщения"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")


def print_test_header(test_name: str):
    """Вывод заголовка теста"""
    print(f"\n{Colors.BOLD}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}🧪 Тест: {test_name}{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 70}{Colors.END}\n")


def check_api_health() -> bool:
    """Проверка доступности API"""
    try:
        response = httpx.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print_success("API сервер доступен")
            return True
        else:
            print_error(f"API сервер вернул код {response.status_code}")
            return False
    except httpx.ConnectError:
        print_error("API сервер недоступен. Запустите: PYTHONPATH=. uvicorn backend.app.main:app --reload")
        return False
    except Exception as e:
        print_error(f"Ошибка проверки API: {e}")
        return False


def test_json_upload(json_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Тест 1: Загрузка JSON формата
    
    Проверяет:
    - Парсинг JSON строки
    - Валидацию структуры
    - Анализ через агента-библиотекаря
    
    Args:
        json_path: Путь к JSON файлу (опционально, если не указан, используется встроенный пример)
    """
    print_test_header("Загрузка JSON формата")
    
    # Загружаем JSON из файла или используем встроенный пример
    if json_path:
        json_file = Path(json_path)
        if json_file.exists():
            with open(json_file, "r", encoding="utf-8") as f:
                test_article_json = json.load(f)
            print_info(f"Загружен JSON из файла: {json_path}")
        else:
            print_error(f"JSON файл не найден: {json_path}")
            return {"success": False, "error": "JSON файл не найден"}
    else:
        # Пример JSON статьи для KB
        test_article_json = {
        "title": "Как устранить stringing (сопли) при печати PLA",
        "content": """
        Stringing (сопли) - это проблема, когда между деталями появляются тонкие ниточки пластика.
        
        Причины:
        - Слишком высокая температура сопла
        - Недостаточная retraction
        - Слишком медленная скорость retraction
        
        Решения:
        1. Уменьшите температуру сопла на 5-10°C
        2. Увеличьте retraction до 6-8 мм
        3. Увеличьте скорость retraction до 45-60 мм/с
        4. Включите функцию "Wipe" в настройках слайсера
        
        Эти настройки подходят для большинства принтеров с прямым экструдером (Ender-3, Prusa i3).
        """,
        "url": "https://3dtoday.ru/blogs/test/stringing-pla",
        "section": "Техничка",
        "date": "2024-01-15",
        "problem_type": "stringing",
        "printer_models": ["Ender-3", "Prusa i3"],
        "materials": ["PLA"],
        "symptoms": ["ниточки между деталями", "сопли", "паутина"],
        "solutions": [
            {
                "parameter": "retraction_length",
                "value": 6,
                "unit": "mm",
                "description": "Увеличьте retraction до 6 мм"
            },
            {
                "parameter": "retraction_speed",
                "value": 45,
                "unit": "mm/s",
                "description": "Скорость retraction 45 мм/с"
            },
            {
                "parameter": "nozzle_temperature",
                "value": -5,
                "unit": "°C",
                "description": "Уменьшите температуру сопла на 5°C"
            }
        ]
    }
    
    try:
        print_info("Отправка JSON на парсинг...")
        
        # Конвертируем JSON в строку для отправки
        json_string = json.dumps(test_article_json, ensure_ascii=False)
        
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse",
                json={
                    "source": json_string,
                    "source_type": "json",
                    "llm_provider": "gemini",  # Используем gemini вместо ollama (ollama может быть недоступен)
                    "timeout": 300
                }
            )
            
            if response.status_code != 200:
                print_error(f"Ошибка парсинга JSON: {response.status_code}")
                print_error(f"Ответ: {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            result = response.json()
            
            if not result.get("success"):
                print_error(f"Парсинг не удался: {result.get('error', 'Unknown error')}")
                return {"success": False, "error": result.get("error")}
            
            parsed_doc = result.get("parsed_document", {})
            review = result.get("review", {})
            
            print_success("JSON успешно распарсен")
            print_info(f"Заголовок: {parsed_doc.get('title', 'N/A')}")
            print_info(f"Раздел: {parsed_doc.get('section', 'N/A')}")
            print_info(f"Релевантность: {review.get('relevance_score', 0):.2f}")
            print_info(f"Качество: {review.get('quality_score', 0):.2f}")
            
            # Проверяем, что метаданные извлечены
            summary = review.get("summary", {})
            if summary.get("problem_type"):
                print_success(f"Тип проблемы извлечен: {summary['problem_type']}")
            if summary.get("printer_models"):
                print_success(f"Модели принтеров извлечены: {', '.join(summary['printer_models'])}")
            if summary.get("materials"):
                print_success(f"Материалы извлечены: {', '.join(summary['materials'])}")
            
            return {
                "success": True,
                "parsed_document": parsed_doc,
                "review": review
            }
            
    except httpx.TimeoutException:
        print_error("Таймаут при парсинге JSON")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        print_error(f"Ошибка теста JSON: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def test_pdf_upload(pdf_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Тест 2: Загрузка PDF формата с картинками
    
    Проверяет:
    - Парсинг PDF файла (через URL или путь к файлу)
    - Извлечение текста
    - Извлечение изображений
    - Анализ через агента-библиотекаря
    
    Args:
        pdf_path: Путь к PDF файлу или URL PDF (если None, используется тестовый URL)
    """
    print_test_header("Загрузка PDF формата с картинками")
    
    # Если PDF не указан, используем тестовый URL или путь
    if not pdf_path:
        # Можно использовать тестовый PDF URL или локальный файл
        print_info("PDF файл не указан. Используйте --pdf для указания пути или URL")
        print_info("Пример: python tools/test_admin_ui_functionality.py --pdf path/to/test.pdf")
        print_info("Или: python tools/test_admin_ui_functionality.py --pdf https://example.com/doc.pdf")
        return {"success": False, "error": "PDF файл не указан", "skipped": True}
    
    # Проверяем, это URL или путь к файлу
    is_url = pdf_path.startswith("http://") or pdf_path.startswith("https://")
    
    if not is_url:
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            print_error(f"PDF файл не найден: {pdf_path}")
            return {"success": False, "error": "PDF файл не найден"}
    
    try:
        print_info(f"Загрузка PDF: {pdf_path}")
        
        # Отправляем через API parse endpoint (он поддерживает и файлы, и URL)
        with httpx.Client(timeout=TIMEOUT) as client:
            # Если это URL, отправляем как обычный запрос
            if is_url:
                response = client.post(
                    f"{API_BASE_URL}/api/kb/articles/parse",
                    json={
                        "source": pdf_path,
                        "source_type": "pdf",
                        "llm_provider": "gemini",  # Используем Gemini для PDF (лучше для анализа изображений)
                        "timeout": 300,
                        "max_pages": 30  # Ограничиваем до 30 страниц для теста
                    }
                )
            else:
                # Если это файл, читаем и отправляем как строку пути
                # API должен поддерживать локальные пути или мы можем использовать file upload
                # Пока используем путь к файлу как строку
                response = client.post(
                    f"{API_BASE_URL}/api/kb/articles/parse",
                    json={
                        "source": str(Path(pdf_path).absolute()),
                        "source_type": "pdf",
                        "llm_provider": "gemini",  # Используем Gemini для теста
                        "timeout": 300,
                        "max_pages": 30  # Ограничиваем до 30 страниц для теста
                    }
                )
            
            if response.status_code != 200:
                print_error(f"Ошибка парсинга PDF: {response.status_code}")
                
                # Пытаемся получить детали ошибки из ответа
                try:
                    error_detail = response.json().get('detail', response.text)
                except:
                    error_detail = response.text[:500] if len(response.text) > 500 else response.text
                
                print_error(f"Детали ошибки: {error_detail}")
                
                # Проверяем типичные причины ошибок
                error_lower = error_detail.lower() if isinstance(error_detail, str) else ""
                if "не удалось распарсить" in error_lower or "parse" in error_lower:
                    print_info("💡 Возможно, PDF файл поврежден или имеет нестандартный формат")
                elif "не найден" in error_lower or "not found" in error_lower or "no such file" in error_lower:
                    print_info("💡 Файл не найден - проверьте путь к файлу")
                elif "pypdf2" in error_lower or "import" in error_lower:
                    print_info("💡 Возможно, библиотека PyPDF2 не установлена: pip install PyPDF2")
                elif "permission" in error_lower or "доступ" in error_lower:
                    print_info("💡 Проблема с правами доступа к файлу")
                
                return {"success": False, "error": f"HTTP {response.status_code}: {error_detail[:200]}"}
            
            result = response.json()
            
            if not result.get("success"):
                print_error(f"Парсинг не удался: {result.get('error', 'Unknown error')}")
                return {"success": False, "error": result.get("error")}
            
            parsed_doc = result.get("parsed_document", {})
            review = result.get("review", {})
            
            print_success("PDF успешно распарсен")
            print_info(f"Заголовок: {parsed_doc.get('title', 'N/A')}")
            print_info(f"Размер контента: {len(parsed_doc.get('content', ''))} символов")
            
            # Проверяем наличие изображений
            images = parsed_doc.get("images", [])
            if images:
                print_success(f"Изображений извлечено: {len(images)}")
                for i, img_url in enumerate(images[:3], 1):
                    print_info(f"  {i}. {img_url}")
            else:
                print_info("Изображения не найдены в PDF")
            
            print_info(f"Релевантность: {review.get('relevance_score', 0):.2f}")
            print_info(f"Качество: {review.get('quality_score', 0):.2f}")
            
            return {
                "success": True,
                "parsed_document": parsed_doc,
                "review": review,
                "images_count": len(images)
            }
            
    except httpx.TimeoutException:
        print_error("Таймаут при парсинге PDF")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        print_error(f"Ошибка теста PDF: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def test_url_upload(test_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Тест 3: Загрузка URL
    
    Проверяет:
    - Парсинг URL через обычный парсер
    - Парсинг URL через LLM (GPT-4o/Gemini)
    - Извлечение контента и метаданных
    - Анализ через агента-библиотекаря
    
    Args:
        test_url: URL для тестирования (если None, используется тестовый URL)
    """
    print_test_header("Загрузка URL")
    
    if not test_url:
        # Используем тестовый URL с 3dtoday.ru
        test_url = "https://3dtoday.ru/blogs/news3dtoday/ucenye-dvfu-sozdayut-prodvinutye-medicinskie-simulyatory"
        print_info(f"Используется тестовый URL: {test_url}")
    
    try:
        # Тест 3.1: Обычный парсинг URL
        print_info("\n📋 Тест 3.1: Обычный парсинг URL")
        
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse",
                json={
                    "source": test_url,
                    "source_type": "url",
                    "llm_provider": "ollama",
                    "timeout": 300
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    parsed_doc = result.get("parsed_document", {})
                    review = result.get("review", {})
                    
                    print_success("URL успешно распарсен (обычный метод)")
                    print_info(f"Заголовок: {parsed_doc.get('title', 'N/A')}")
                    print_info(f"Релевантность: {review.get('relevance_score', 0):.2f}")
                    
                    url_result_normal = {
                        "success": True,
                        "parsed_document": parsed_doc,
                        "review": review
                    }
                else:
                    print_error(f"Парсинг не удался: {result.get('error', 'Unknown error')}")
                    url_result_normal = {"success": False, "error": result.get("error")}
            else:
                print_error(f"Ошибка парсинга URL: {response.status_code}")
                url_result_normal = {"success": False, "error": f"HTTP {response.status_code}"}
        
        # Тест 3.2: Парсинг через LLM (GPT-4o/Gemini)
        print_info("\n🤖 Тест 3.2: Парсинг URL через LLM")
        print_info("💡 Примечание: LLM парсинг требует API ключи (GEMINI_API_KEY или OPENAI_API_KEY)")
        
        # Пробуем через Gemini (если доступен)
        llm_providers = ["gemini", "openai"]
        url_result_llm = None
        
        for provider in llm_providers:
            try:
                print_info(f"\nПробуем провайдер: {provider}")
                
                with httpx.Client(timeout=TIMEOUT) as client:
                    response = client.post(
                        f"{API_BASE_URL}/api/kb/articles/parse_with_llm",
                        json={
                            "url": test_url,
                            "llm_provider": provider,
                            "model": "gemini-3-pro-preview" if provider == "gemini" else "gpt-4o"
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            parsed_doc = result.get("parsed_document", {})
                            
                            print_success(f"URL успешно проанализирован через {provider.upper()}")
                            print_info(f"Заголовок: {parsed_doc.get('title', 'N/A')}")
                            print_info(f"Релевантность: {parsed_doc.get('relevance_score', 0):.2f}")
                            
                            url_result_llm = {
                                "success": True,
                                "provider": provider,
                                "parsed_document": parsed_doc
                            }
                            break
                        else:
                            error_msg = result.get('error', result.get('detail', 'Unknown error'))
                            print_error(f"Парсинг через {provider} не удался: {error_msg}")
                    else:
                        # Пытаемся получить детали ошибки из ответа
                        try:
                            error_detail = response.json().get('detail', response.text)
                        except:
                            error_detail = response.text[:500] if len(response.text) > 500 else response.text
                        
                        print_error(f"Ошибка парсинга через {provider}: HTTP {response.status_code}")
                        if error_detail:
                            print_error(f"Детали: {error_detail}")
                        
                        # Проверяем, не связана ли ошибка с отсутствием API ключей
                        error_lower = error_detail.lower() if isinstance(error_detail, str) else ""
                        if "api_key" in error_lower or "api key" in error_lower or "не установлен" in error_lower:
                            print_info(f"💡 Не установлен API ключ для {provider.upper()}")
                            print_info(f"   Установите {provider.upper()}_API_KEY в config.env")
                        elif "timeout" in error_lower or "timed out" in error_lower:
                            print_info("💡 Превышено время ожидания - попробуйте увеличить таймаут")
                        elif "connection" in error_lower or "connection refused" in error_lower:
                            print_info("💡 Проблема с подключением к API провайдера")
                        elif "valueerror" in error_lower or "неподдерживаемый провайдер" in error_lower:
                            print_info("💡 Проблема с конфигурацией провайдера")
                        
            except httpx.TimeoutException:
                print_error(f"Таймаут при парсинге через {provider}")
                print_info("💡 Попробуйте увеличить таймаут или проверить доступность API")
                continue
            except Exception as e:
                print_error(f"Ошибка при парсинге через {provider}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        if not url_result_llm:
            print_info("\n⚠️ LLM парсинг недоступен")
            print_info("💡 Для использования LLM парсинга:")
            print_info("   1. Установите GEMINI_API_KEY или OPENAI_API_KEY в config.env")
            print_info("   2. Убедитесь, что провайдер доступен")
            print_info("   3. Обычный парсинг (без LLM) работает и этого достаточно для большинства случаев")
        
        return {
            "success": url_result_normal.get("success", False) or (url_result_llm and url_result_llm.get("success", False)),
            "normal_parse": url_result_normal,
            "llm_parse": url_result_llm
        }
        
    except httpx.TimeoutException:
        print_error("Таймаут при парсинге URL")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        print_error(f"Ошибка теста URL: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def main():
    """Главная функция запуска тестов"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Тесты функционала веб-интерфейса администрирования KB")
    parser.add_argument("--json", type=str, nargs="?", const=True, help="Запустить тест JSON (опционально указать путь к JSON файлу)")
    parser.add_argument("--pdf", type=str, help="Путь к PDF файлу или URL для теста")
    parser.add_argument("--url", type=str, help="URL для теста")
    parser.add_argument("--skip-health", action="store_true", help="Пропустить проверку здоровья API")
    
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("=" * 70)
    print("🧪 Тесты функционала веб-интерфейса администрирования KB")
    print("=" * 70)
    print(f"{Colors.END}")
    
    # Проверка здоровья API
    if not args.skip_health:
        if not check_api_health():
            print_error("Не удалось подключиться к API. Завершение тестов.")
            return 1
    
    results = {}
    
    # Запуск тестов
    json_path = None
    if args.json:
        if isinstance(args.json, str):
            json_path = args.json
        else:
            # Пробуем использовать тестовый файл по умолчанию
            default_json = Path(__file__).parent / "test_data" / "sample_article.json"
            if default_json.exists():
                json_path = str(default_json)
    
    if args.json or not (args.pdf or args.url):
        results["json"] = test_json_upload(json_path)
    
    if args.pdf or (not args.json and not args.url):
        pdf_result = test_pdf_upload(args.pdf)
        if not pdf_result.get("skipped"):
            results["pdf"] = pdf_result
    
    if args.url or (not args.json and not args.pdf):
        results["url"] = test_url_upload(args.url)
    
    # Итоги
    print(f"\n{Colors.BOLD}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}📊 Итоги тестирования{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 70}{Colors.END}\n")
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r.get("success", False))
    
    for test_name, result in results.items():
        if result.get("success", False):
            print_success(f"{test_name.upper()}: ПРОЙДЕН")
        else:
            print_error(f"{test_name.upper()}: ПРОВАЛЕН - {result.get('error', 'Unknown error')}")
    
    print(f"\n{Colors.BOLD}Всего тестов: {total_tests}{Colors.END}")
    print(f"{Colors.GREEN if passed_tests == total_tests else Colors.YELLOW}Пройдено: {passed_tests}/{total_tests}{Colors.END}")
    
    return 0 if passed_tests == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
