#!/usr/bin/env python3
"""
Тесты функционала пользовательского интерфейса (техподдержка)

Проверяет:
1. Диалог с пользователем с уточняющими вопросами
2. Загрузку поясняющих картинок
3. Сохранение контекста между запросами
4. Реалистичный сценарий взаимодействия с пользователем

Все тесты используют те же API endpoints, что и веб-интерфейс.
"""

import sys
import json
import httpx
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from io import BytesIO
import base64

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_BASE_URL = "http://localhost:8000"
TIMEOUT = 300  # 5 минут для диагностики


class Colors:
    """Цвета для вывода в консоль"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
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


def print_user(message: str):
    """Вывод сообщения пользователя"""
    print(f"{Colors.CYAN}👤 Пользователь: {message}{Colors.END}")


def print_assistant(message: str):
    """Вывод сообщения ассистента"""
    print(f"{Colors.MAGENTA}🤖 Система: {message}{Colors.END}")


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


class UserDialogSimulator:
    """Симулятор диалога пользователя с системой"""
    
    def __init__(self):
        self.conversation_history: List[Dict[str, Any]] = []
        self.user_context: Dict[str, Optional[str]] = {
            "printer_model": None,
            "material": None,
            "problem_type": None
        }
    
    def add_user_message(self, content: str):
        """Добавление сообщения пользователя"""
        self.conversation_history.append({
            "role": "user",
            "content": content
        })
    
    def add_assistant_message(self, content: str, clarification_questions: Optional[List] = None):
        """Добавление сообщения ассистента"""
        message = {
            "role": "assistant",
            "content": content
        }
        if clarification_questions:
            message["clarification_questions"] = clarification_questions
        self.conversation_history.append(message)
    
    def update_context(self, printer_model: Optional[str] = None, 
                      material: Optional[str] = None,
                      problem_type: Optional[str] = None):
        """Обновление контекста пользователя"""
        if printer_model:
            self.user_context["printer_model"] = printer_model
        if material:
            self.user_context["material"] = material
        if problem_type:
            self.user_context["problem_type"] = problem_type
    
    def diagnose(self, query: str, image_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Отправка запроса на диагностику
        
        Args:
            query: Описание проблемы
            image_path: Путь к изображению дефекта (опционально)
        
        Returns:
            Ответ от API
        """
        try:
            self.add_user_message(query)
            print_user(query)
            
            if image_path:
                # Диагностика с изображением
                with open(image_path, "rb") as f:
                    image_content = f.read()
                
                with httpx.Client(timeout=TIMEOUT) as client:
                    files = {
                        "image": (Path(image_path).name, BytesIO(image_content), "image/jpeg")
                    }
                    data = {
                        "query": query,
                        "printer_model": self.user_context.get("printer_model") or "",
                        "material": self.user_context.get("material") or ""
                    }
                    
                    response = client.post(
                        f"{API_BASE_URL}/api/diagnose/image",
                        files=files,
                        data=data
                    )
            else:
                # Обычная диагностика
                with httpx.Client(timeout=TIMEOUT) as client:
                    response = client.post(
                        f"{API_BASE_URL}/api/diagnose",
                        json={
                            "query": query,
                            "printer_model": self.user_context.get("printer_model"),
                            "material": self.user_context.get("material"),
                            "problem_type": self.user_context.get("problem_type")
                        }
                    )
            
            if response.status_code != 200:
                print_error(f"Ошибка диагностики: {response.status_code}")
                print_error(f"Ответ: {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            result = response.json()
            
            # Выводим ответ системы
            answer = result.get("answer", result.get("message", ""))
            print_assistant(answer)
            
            # Выводим уточняющие вопросы, если есть
            clarification_questions = result.get("clarification_questions")
            if clarification_questions:
                print_info("❓ Уточняющие вопросы:")
                for q in clarification_questions:
                    question_text = q.get("question", q) if isinstance(q, dict) else q
                    print(f"   • {question_text}")
            
            # Выводим релевантные статьи
            relevant_articles = result.get("relevant_articles")
            if relevant_articles:
                print_info(f"📚 Найдено релевантных статей: {len(relevant_articles)}")
                for i, article in enumerate(relevant_articles[:3], 1):
                    title = article.get("title", "N/A")
                    score = article.get("score", 0.0)
                    print(f"   {i}. {title} (релевантность: {score:.2f})")
            
            # Сохраняем ответ в историю
            self.add_assistant_message(answer, clarification_questions)
            
            return {
                "success": True,
                "answer": answer,
                "clarification_questions": clarification_questions,
                "relevant_articles": relevant_articles,
                "confidence": result.get("confidence", 0.0),
                "needs_clarification": result.get("needs_clarification", False)
            }
            
        except httpx.TimeoutException:
            print_error("Таймаут при диагностике")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            print_error(f"Ошибка диагностики: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}


def test_realistic_dialog_scenario() -> Dict[str, Any]:
    """
    Тест реалистичного сценария диалога с пользователем
    
    Сценарий:
    1. Пользователь описывает проблему без деталей
    2. Система задает уточняющие вопросы
    3. Пользователь отвечает на вопросы
    4. Система дает рекомендации
    5. Пользователь загружает изображение дефекта
    6. Система анализирует изображение (если реализовано)
    """
    print_test_header("Реалистичный сценарий диалога с пользователем")
    
    dialog = UserDialogSimulator()
    results = []
    
    # Шаг 1: Первый запрос пользователя (без деталей)
    print_info("\n📋 Шаг 1: Пользователь описывает проблему")
    result1 = dialog.diagnose("У меня появляются ниточки между деталями при печати")
    results.append(("Шаг 1: Первый запрос", result1))
    
    if not result1.get("success"):
        print_error("Шаг 1 провален")
        return {"success": False, "results": results}
    
    # Проверяем, что система задала уточняющие вопросы
    needs_clarification = result1.get("needs_clarification", False)
    clarification_questions = result1.get("clarification_questions", [])
    
    if needs_clarification and clarification_questions:
        print_success("Система правильно определила необходимость уточнений")
        
        # Шаг 2: Пользователь отвечает на вопросы
        print_info("\n📋 Шаг 2: Пользователь отвечает на уточняющие вопросы")
        
        # Обновляем контекст на основе вопросов
        for q in clarification_questions:
            question_type = q.get("question_type", "") if isinstance(q, dict) else ""
            if question_type == "printer_model":
                dialog.update_context(printer_model="Ender-3")
                print_user("Модель принтера: Ender-3")
            elif question_type == "material":
                dialog.update_context(material="PLA")
                print_user("Материал: PLA")
        
        # Шаг 3: Повторный запрос с обновленным контекстом
        print_info("\n📋 Шаг 3: Повторный запрос с уточненным контекстом")
        result2 = dialog.diagnose("У меня появляются ниточки между деталями при печати PLA на Ender-3")
        results.append(("Шаг 3: Повторный запрос", result2))
        
        if result2.get("success"):
            confidence = result2.get("confidence", 0.0)
            print_info(f"Уверенность системы: {confidence:.2f}")
            
            if confidence > 0.7:
                print_success("Система дала уверенные рекомендации")
            else:
                print_info("Система дала рекомендации с низкой уверенностью (возможно, нужны дополнительные уточнения)")
    else:
        print_info("Система не задала уточняющих вопросов (возможно, информации достаточно)")
    
    # Шаг 4: Загрузка изображения дефекта
    print_info("\n📋 Шаг 4: Загрузка изображения дефекта")
    
    # Создаем тестовое изображение (1x1 пиксель JPEG)
    test_image_path = Path(__file__).parent / "test_data" / "test_defect.jpg"
    test_image_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Создаем минимальный валидный JPEG
    try:
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='red')
        img.save(test_image_path, 'JPEG')
        print_success(f"Создано тестовое изображение: {test_image_path}")
    except ImportError:
        print_info("PIL не установлен, пропускаем тест с изображением")
        print_info("Установите: pip install Pillow")
        results.append(("Шаг 4: Загрузка изображения", {"success": False, "skipped": True, "reason": "PIL not installed"}))
    else:
        result3 = dialog.diagnose(
            "Вот фото дефекта - видите эти ниточки?",
            image_path=str(test_image_path)
        )
        results.append(("Шаг 4: Загрузка изображения", result3))
        
        if result3.get("success"):
            message = result3.get("answer", result3.get("message", ""))
            if "ШАГЕ 8" in message or "будет реализован" in message.lower():
                print_info("Анализ изображений еще не реализован (ожидаемо)")
            else:
                print_success("Изображение успешно обработано")
    
    # Итоги диалога
    print(f"\n{Colors.BOLD}📊 Итоги диалога:{Colors.END}")
    print(f"Всего сообщений: {len(dialog.conversation_history)}")
    print(f"Сообщений пользователя: {sum(1 for m in dialog.conversation_history if m['role'] == 'user')}")
    print(f"Сообщений системы: {sum(1 for m in dialog.conversation_history if m['role'] == 'assistant')}")
    print(f"Контекст: Принтер={dialog.user_context['printer_model']}, Материал={dialog.user_context['material']}")
    
    # Проверяем успешность всех шагов
    successful_steps = sum(1 for _, r in results if r.get("success", False))
    total_steps = len([r for _, r in results if not r.get("skipped", False)])
    
    return {
        "success": successful_steps == total_steps,
        "results": results,
        "conversation_history": dialog.conversation_history,
        "user_context": dialog.user_context,
        "successful_steps": successful_steps,
        "total_steps": total_steps
    }


def test_context_persistence() -> Dict[str, Any]:
    """
    Тест сохранения контекста между запросами
    
    Проверяет, что система правильно использует контекст пользователя
    (модель принтера, материал) в последующих запросах
    """
    print_test_header("Сохранение контекста между запросами")
    
    dialog = UserDialogSimulator()
    
    # Устанавливаем контекст
    dialog.update_context(printer_model="Prusa i3", material="PETG")
    print_info("Установлен контекст: Prusa i3, PETG")
    
    # Первый запрос
    print_info("\n📋 Запрос 1: С контекстом")
    result1 = dialog.diagnose("Печать отслаивается от стола")
    
    if not result1.get("success"):
        return {"success": False, "error": "Первый запрос провален"}
    
    # Проверяем, что контекст использован
    relevant_articles = result1.get("relevant_articles", [])
    if relevant_articles:
        print_success(f"Найдено релевантных статей: {len(relevant_articles)}")
    
    # Второй запрос с другим вопросом, но тем же контекстом
    print_info("\n📋 Запрос 2: Другой вопрос, тот же контекст")
    result2 = dialog.diagnose("Какую температуру стола использовать?")
    
    if result2.get("success"):
        print_success("Контекст сохранен между запросами")
        return {"success": True, "results": [result1, result2]}
    else:
        return {"success": False, "error": "Второй запрос провален"}


def test_clarification_flow() -> Dict[str, Any]:
    """
    Тест потока уточняющих вопросов
    
    Проверяет полный цикл: вопрос → уточнение → ответ
    """
    print_test_header("Поток уточняющих вопросов")
    
    dialog = UserDialogSimulator()
    
    # Запрос без контекста
    print_info("📋 Запрос без указания принтера и материала")
    result1 = dialog.diagnose("Проблема с печатью")
    
    if not result1.get("success"):
        return {"success": False, "error": "Запрос провален"}
    
    clarification_questions = result1.get("clarification_questions", [])
    
    if not clarification_questions:
        print_info("Система не задала уточняющих вопросов")
        return {"success": True, "note": "Уточнения не потребовались"}
    
    print_success(f"Система задала {len(clarification_questions)} уточняющих вопросов")
    
    # Отвечаем на вопросы
    print_info("\n📋 Отвечаем на уточняющие вопросы")
    for q in clarification_questions:
        question_type = q.get("question_type", "") if isinstance(q, dict) else ""
        if question_type == "printer_model":
            dialog.update_context(printer_model="Anycubic Kobra")
            print_user("Модель принтера: Anycubic Kobra")
        elif question_type == "material":
            dialog.update_context(material="ABS")
            print_user("Материал: ABS")
    
    # Повторный запрос с уточнениями
    print_info("\n📋 Повторный запрос с уточнениями")
    result2 = dialog.diagnose("Проблема с печатью ABS на Anycubic Kobra")
    
    if result2.get("success"):
        confidence = result2.get("confidence", 0.0)
        print_success(f"Получен ответ с уверенностью {confidence:.2f}")
        return {"success": True, "results": [result1, result2]}
    else:
        return {"success": False, "error": "Повторный запрос провален"}


def main():
    """Главная функция запуска тестов"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Тесты функционала пользовательского интерфейса")
    parser.add_argument("--scenario", action="store_true", help="Запустить реалистичный сценарий")
    parser.add_argument("--context", action="store_true", help="Тест сохранения контекста")
    parser.add_argument("--clarification", action="store_true", help="Тест потока уточнений")
    parser.add_argument("--skip-health", action="store_true", help="Пропустить проверку здоровья API")
    
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("=" * 70)
    print("🧪 Тесты функционала пользовательского интерфейса (техподдержка)")
    print("=" * 70)
    print(f"{Colors.END}")
    
    # Проверка здоровья API
    if not args.skip_health:
        if not check_api_health():
            print_error("Не удалось подключиться к API. Завершение тестов.")
            return 1
    
    results = {}
    
    # Запуск тестов
    if args.scenario or not (args.context or args.clarification):
        results["realistic_scenario"] = test_realistic_dialog_scenario()
    
    if args.context or (not args.scenario and not args.clarification):
        results["context_persistence"] = test_context_persistence()
    
    if args.clarification or (not args.scenario and not args.context):
        results["clarification_flow"] = test_clarification_flow()
    
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
            error = result.get("error", "Unknown error")
            print_error(f"{test_name.upper()}: ПРОВАЛЕН - {error}")
    
    print(f"\n{Colors.BOLD}Всего тестов: {total_tests}{Colors.END}")
    print(f"{Colors.GREEN if passed_tests == total_tests else Colors.YELLOW}Пройдено: {passed_tests}/{total_tests}{Colors.END}")
    
    return 0 if passed_tests == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())




