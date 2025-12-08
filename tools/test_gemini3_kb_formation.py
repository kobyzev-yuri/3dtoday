#!/usr/bin/env python3
"""
Тестовый скрипт для проверки ProxyAPI Gemini 3 на формирование базы знаний по URL
"""

import sys
import asyncio
import json
import logging
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "app"))

from services.llm_url_analyzer import LLMURLAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_gemini3_kb_formation(url: str):
    """
    Тестирование формирования базы знаний через ProxyAPI Gemini 3
    
    Args:
        url: URL для анализа
    """
    print("="*80)
    print("🧪 ТЕСТ: ProxyAPI Gemini 3 - Формирование базы знаний")
    print("="*80)
    print(f"\n📌 URL для анализа: {url}\n")
    
    try:
        # Инициализация анализатора с Gemini 3
        analyzer = LLMURLAnalyzer(
            llm_provider="gemini",
            model="gemini-3-pro-preview"
        )
        
        print(f"✅ Анализатор инициализирован:")
        print(f"   Провайдер: {analyzer.llm_provider}")
        print(f"   Модель: {analyzer.model}")
        print(f"   Таймаут: {analyzer.timeout} сек\n")
        
        # Анализ URL
        print("🔍 Начинаю анализ URL через ProxyAPI Gemini 3...")
        print("   (Это может занять некоторое время)\n")
        
        result = await analyzer.analyze_url(url)
        
        if result:
            print("\n" + "="*80)
            print("✅ УСПЕХ: URL успешно проанализирован!")
            print("="*80)
            
            # Выводим структурированные данные
            print("\n📊 РЕЗУЛЬТАТЫ АНАЛИЗА:\n")
            
            print(f"📝 Заголовок: {result.get('title', 'не указан')}")
            print(f"🔗 URL: {result.get('url', 'не указан')}")
            print(f"📂 Раздел: {result.get('section', 'не указан')}")
            print(f"📄 Тип контента: {result.get('content_type', 'не указан')}")
            print(f"⭐ Релевантность: {result.get('relevance_score', 0):.2f}")
            print(f"✨ Качество: {result.get('quality_score', 0):.2f}")
            print(f"✅ Релевантна: {'Да' if result.get('is_relevant', False) else 'Нет'}")
            
            if result.get('abstract'):
                print(f"\n📋 Краткое изложение:")
                print(f"   {result['abstract']}")
            
            if result.get('problem'):
                print(f"\n🔧 Проблема:")
                print(f"   {result['problem']}")
            
            if result.get('symptoms'):
                print(f"\n⚠️  Симптомы:")
                for symptom in result['symptoms']:
                    print(f"   - {symptom}")
            
            if result.get('solutions'):
                print(f"\n💡 Решения ({len(result['solutions'])}):")
                for i, solution in enumerate(result['solutions'], 1):
                    print(f"   {i}. {solution.get('description', 'без описания')}")
                    if solution.get('parameters'):
                        print(f"      Параметры: {solution['parameters']}")
            
            if result.get('printer_models'):
                print(f"\n🖨️  Модели принтеров:")
                for model in result['printer_models']:
                    print(f"   - {model}")
            
            if result.get('materials'):
                print(f"\n🧪 Материалы:")
                for material in result['materials']:
                    print(f"   - {material}")
            
            if result.get('images'):
                print(f"\n🖼️  Изображения ({len(result['images'])}):")
                for i, img in enumerate(result['images'], 1):
                    print(f"   {i}. URL: {img.get('url', 'не указан')}")
                    if img.get('description'):
                        print(f"      Описание: {img['description']}")
            
            if result.get('tags'):
                print(f"\n🏷️  Теги:")
                print(f"   {', '.join(result['tags'])}")
            
            # Выводим длину контента
            content = result.get('content', '')
            if content:
                print(f"\n📄 Длина контента: {len(content)} символов")
                print(f"   Первые 500 символов:")
                print(f"   {content[:500]}...")
            
            # Сохраняем полный результат в JSON
            output_file = Path(__file__).parent / "gemini3_test_result.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 Полный результат сохранен в: {output_file}")
            
            # Проверка качества результата
            print("\n" + "="*80)
            print("🔍 ПРОВЕРКА КАЧЕСТВА РЕЗУЛЬТАТА:")
            print("="*80)
            
            checks = []
            
            # Проверка обязательных полей
            required_fields = ['title', 'content', 'url', 'section', 'relevance_score', 'is_relevant']
            for field in required_fields:
                if field in result and result[field]:
                    checks.append(("✅", f"Поле '{field}' присутствует"))
                else:
                    checks.append(("❌", f"Поле '{field}' отсутствует или пустое"))
            
            # Проверка релевантности
            relevance_score = result.get('relevance_score', 0)
            if relevance_score >= 0.7:
                checks.append(("✅", f"Высокая релевантность ({relevance_score:.2f})"))
            elif relevance_score >= 0.5:
                checks.append(("⚠️", f"Средняя релевантность ({relevance_score:.2f})"))
            else:
                checks.append(("❌", f"Низкая релевантность ({relevance_score:.2f})"))
            
            # Проверка наличия структурированных данных
            if result.get('solutions'):
                checks.append(("✅", f"Найдено решений: {len(result['solutions'])}"))
            else:
                checks.append(("⚠️", "Решения не найдены"))
            
            if result.get('symptoms'):
                checks.append(("✅", f"Найдено симптомов: {len(result['symptoms'])}"))
            else:
                checks.append(("⚠️", "Симптомы не найдены"))
            
            for status, message in checks:
                print(f"   {status} {message}")
            
            print("\n" + "="*80)
            print("✅ ТЕСТ ЗАВЕРШЕН")
            print("="*80)
            
            return result
            
        else:
            print("\n" + "="*80)
            print("❌ ОШИБКА: Не удалось проанализировать URL")
            print("="*80)
            return None
            
    except Exception as e:
        print("\n" + "="*80)
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        print("="*80)
        logger.exception("Детали ошибки:")
        return None


async def main():
    """Главная функция"""
    import sys
    
    if len(sys.argv) < 2:
        print("Использование: python test_gemini3_kb_formation.py <URL>")
        print("\nПримеры:")
        print("  python test_gemini3_kb_formation.py https://3dtoday.ru/blogs/user123/post456")
        print("  python test_gemini3_kb_formation.py https://habr.com/ru/articles/123456/")
        sys.exit(1)
    
    url = sys.argv[1]
    
    result = await test_gemini3_kb_formation(url)
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


