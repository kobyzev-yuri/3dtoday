#!/usr/bin/env python3
"""
Быстрое тестирование всех методов загрузки документов в KB

Тестирует:
1. URL через LLM (Gemini)
2. URL обычный парсинг
3. Ручной ввод (JSON)
4. Файлы (TXT, MD) - если есть

Запуск:
    python tools/test_all_upload_methods.py
"""

import sys
import json
import httpx
from pathlib import Path
from typing import Dict, Any

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_BASE_URL = "http://localhost:8000"
TIMEOUT = 600  # 10 минут


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg): print(f"{Colors.GREEN}✅ {msg}{Colors.END}")
def print_error(msg): print(f"{Colors.RED}❌ {msg}{Colors.END}")
def print_info(msg): print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")
def print_header(msg): print(f"\n{Colors.BOLD}{'='*70}{Colors.END}\n{Colors.BOLD}{msg}{Colors.END}\n{Colors.BOLD}{'='*70}{Colors.END}\n")


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


def test_url_with_llm(url: str, provider: str = "gemini") -> Dict[str, Any]:
    """Тест 1: URL через LLM"""
    print_header("Тест 1: URL через LLM (Gemini)")
    print_info(f"URL: {url}")
    print_info(f"Провайдер: {provider}")
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse_with_llm",
                json={
                    "url": url,
                    "llm_provider": provider,
                    "model": "gemini-3-pro-preview" if provider == "gemini" else "gpt-4o"
                }
            )
            
            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    doc = result.get("parsed_document", {})
                    print_success("Статья успешно распарсена через LLM")
                    print_info(f"Заголовок: {doc.get('title', 'N/A')}")
                    print_info(f"Релевантность: {doc.get('relevance_score', 0):.2f}")
                    
                    images = doc.get("images", [])
                    if images:
                        print_success(f"Изображений извлечено: {len(images)}")
                    else:
                        print_info("Изображения не найдены")
                    
                    return {"success": True, "result": result}
                else:
                    print_error(f"Парсинг не удался: {result.get('error', 'Unknown')}")
                    return {"success": False, "error": result.get("error")}
            else:
                error = resp.json().get('detail', resp.text) if resp.headers.get('content-type', '').startswith('application/json') else resp.text
                print_error(f"HTTP {resp.status_code}: {error[:200]}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def test_url_normal(url: str) -> Dict[str, Any]:
    """Тест 2: URL обычный парсинг"""
    print_header("Тест 2: URL обычный парсинг")
    print_info(f"URL: {url}")
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse",
                json={
                    "source": url,
                    "source_type": "url",
                    "llm_provider": "ollama"
                }
            )
            
            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    doc = result.get("parsed_document", {})
                    print_success("Статья успешно распарсена")
                    print_info(f"Заголовок: {doc.get('title', 'N/A')}")
                    return {"success": True, "result": result}
                else:
                    print_error(f"Парсинг не удался: {result.get('error', 'Unknown')}")
                    return {"success": False, "error": result.get("error")}
            else:
                error = resp.json().get('detail', resp.text) if resp.headers.get('content-type', '').startswith('application/json') else resp.text
                print_error(f"HTTP {resp.status_code}: {error[:200]}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return {"success": False, "error": str(e)}


def test_manual_input() -> Dict[str, Any]:
    """Тест 3: Ручной ввод (JSON)"""
    print_header("Тест 3: Ручной ввод (JSON)")
    
    # Используем sample_article.json
    json_path = Path(__file__).parent / "test_data" / "sample_article.json"
    if not json_path.exists():
        print_error(f"Файл не найден: {json_path}")
        return {"success": False, "error": "File not found"}
    
    with open(json_path, "r", encoding="utf-8") as f:
        article_data = json.load(f)
    
    print_info(f"Загружен JSON: {json_path}")
    print_info(f"Заголовок: {article_data.get('title', 'N/A')}")
    
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
                    print_success("Статья успешно добавлена в KB")
                    print_info(f"Article ID: {result.get('article_id', 'N/A')}")
                    return {"success": True, "result": result}
                else:
                    print_error(f"Добавление не удалось: {result.get('error', 'Unknown')}")
                    return {"success": False, "error": result.get("error")}
            else:
                error = resp.json().get('detail', resp.text) if resp.headers.get('content-type', '').startswith('application/json') else resp.text
                print_error(f"HTTP {resp.status_code}: {error[:200]}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def test_file_upload(file_path: Path, source_type: str) -> Dict[str, Any]:
    """Тест 4: Загрузка файла"""
    print_header(f"Тест 4: Загрузка файла ({source_type.upper()})")
    print_info(f"Файл: {file_path}")
    
    if not file_path.exists():
        print_error(f"Файл не найден: {file_path}")
        return {"success": False, "error": "File not found", "skipped": True}
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # Читаем файл
            with open(file_path, "rb") as f:
                file_content = f.read()
            
            # Отправляем как строку пути (API должен поддерживать локальные пути)
            resp = client.post(
                f"{API_BASE_URL}/api/kb/articles/parse",
                json={
                    "source": str(file_path.absolute()),
                    "source_type": source_type,
                    "llm_provider": "ollama"
                }
            )
            
            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    doc = result.get("parsed_document", {})
                    print_success(f"Файл успешно распарсен")
                    print_info(f"Заголовок: {doc.get('title', 'N/A')}")
                    return {"success": True, "result": result}
                else:
                    print_error(f"Парсинг не удался: {result.get('error', 'Unknown')}")
                    return {"success": False, "error": result.get("error")}
            else:
                error = resp.json().get('detail', resp.text) if resp.headers.get('content-type', '').startswith('application/json') else resp.text
                print_error(f"HTTP {resp.status_code}: {error[:200]}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return {"success": False, "error": str(e)}


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Тестирование всех методов загрузки документов")
    parser.add_argument("--skip-health", action="store_true", help="Пропустить проверку API")
    parser.add_argument("--llm-only", action="store_true", help="Только тест через LLM")
    parser.add_argument("--url", type=str, help="URL для тестирования")
    
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("=" * 70)
    print("🧪 Тестирование всех методов загрузки документов в KB")
    print("=" * 70)
    print(f"{Colors.END}\n")
    
    # Проверка API
    if not args.skip_health:
        if not check_api():
            print_error("Не удалось подключиться к API. Завершение.")
            return 1
    
    results = {}
    
    # Тестовые URL из image_urls.json
    test_urls = {
        "llm": "https://www.simplify3d.com/resources/print-quality-troubleshooting/stringing-or-oozing/",
        "normal": "https://all3dp.com/2/3d-printing-warping-how-to-fix-it/"
    }
    
    # Используем переданный URL или дефолтный
    test_url = args.url or test_urls["llm"]
    
    # Тест 1: URL через LLM
    if not args.llm_only:
        results["url_llm"] = test_url_with_llm(test_url, provider="gemini")
    
    # Тест 2: URL обычный парсинг
    if not args.llm_only:
        results["url_normal"] = test_url_normal(test_urls["normal"])
    
    # Тест 3: Ручной ввод
    if not args.llm_only:
        results["manual_input"] = test_manual_input()
    
    # Тест 4: Файлы (если есть)
    if not args.llm_only:
        test_data_dir = Path(__file__).parent / "test_data"
        
        # TXT файл
        txt_file = test_data_dir / "test_article.txt"
        if txt_file.exists():
            results["file_txt"] = test_file_upload(txt_file, "txt")
        else:
            print_info("TXT файл не найден, пропускаем")
        
        # MD файл
        md_file = test_data_dir / "test_article.md"
        if md_file.exists():
            results["file_md"] = test_file_upload(md_file, "md")
        else:
            print_info("MD файл не найден, пропускаем")
    
    # Итоги
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}📊 Итоги тестирования{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")
    
    total = len(results)
    passed = sum(1 for r in results.values() if r.get("success", False))
    skipped = sum(1 for r in results.values() if r.get("skipped", False))
    
    for name, result in results.items():
        if result.get("skipped"):
            print_info(f"{name.upper()}: ПРОПУЩЕН")
        elif result.get("success"):
            print_success(f"{name.upper()}: ПРОЙДЕН")
        else:
            print_error(f"{name.upper()}: ПРОВАЛЕН - {result.get('error', 'Unknown')}")
    
    print(f"\n{Colors.BOLD}Всего тестов: {total}{Colors.END}")
    print(f"{Colors.GREEN if passed == total else Colors.YELLOW}Пройдено: {passed}/{total}{Colors.END}")
    if skipped > 0:
        print(f"{Colors.BLUE}Пропущено: {skipped}{Colors.END}")
    
    return 0 if passed == (total - skipped) else 1


if __name__ == "__main__":
    sys.exit(main())


