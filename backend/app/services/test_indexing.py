#!/usr/bin/env python3
"""
Тест индексации и поиска статей в KB
"""

import asyncio
import sys
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.article_indexer import get_article_indexer
from services.rag_service import get_rag_service

logger = logging.getLogger(__name__)


# Тестовые статьи
TEST_ARTICLES = [
    {
        "article_id": "stringing_pla_001",
        "title": "Как устранить stringing (сопли) при печати PLA",
        "content": """
        Stringing (сопли) - это проблема, когда между деталями появляются тонкие ниточки пластика.
        
        Основные причины:
        1. Слишком высокая температура экструдера
        2. Недостаточный retraction
        3. Слишком медленная скорость печати
        
        Решения:
        1. Уменьшите температуру на 5-10°C
        2. Увеличьте retraction до 6-8 мм
        3. Увеличьте скорость retraction до 45-60 мм/с
        4. Включите функцию "Coasting" в настройках слайсера
        """,
        "url": "https://3dtoday.ru/test/stringing-pla",
        "problem_type": "stringing",
        "printer_models": ["Ender-3", "Ender-3 V2", "Ender-3 Pro"],
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
                "parameter": "temperature",
                "value": 200,
                "unit": "°C",
                "description": "Уменьшите температуру до 200°C"
            }
        ],
        "section": "Техничка",
        "date": "2024-01-15",
        "relevance_score": 0.95
    },
    {
        "article_id": "warping_petg_001",
        "title": "Warping при печати PETG: причины и решения",
        "content": """
        Warping (коробление) - это проблема, когда углы детали отгибаются от стола во время печати.
        
        Основные причины для PETG:
        1. Недостаточная температура стола
        2. Резкое охлаждение первого слоя
        3. Отсутствие brim или skirt
        4. Загрязненный стол
        
        Решения:
        1. Увеличьте температуру стола до 80-85°C для PETG
        2. Отключите вентилятор на первых 3-5 слоях
        3. Используйте brim шириной 5-10 мм
        4. Очистите стол изопропиловым спиртом
        5. Используйте PEI покрытие или клей-карандаш
        """,
        "url": "https://3dtoday.ru/test/warping-petg",
        "problem_type": "warping",
        "printer_models": ["Ender-3", "Anycubic Kobra"],
        "materials": ["PETG"],
        "symptoms": ["отгибание углов", "коробление", "отслоение от стола"],
        "solutions": [
            {
                "parameter": "bed_temperature",
                "value": 80,
                "unit": "°C",
                "description": "Температура стола 80°C"
            },
            {
                "parameter": "fan_speed_first_layers",
                "value": 0,
                "unit": "%",
                "description": "Отключите вентилятор на первых слоях"
            },
            {
                "parameter": "brim_width",
                "value": 5,
                "unit": "mm",
                "description": "Brim шириной 5 мм"
            }
        ],
        "section": "Техничка",
        "date": "2024-01-20",
        "relevance_score": 0.92
    },
    {
        "article_id": "layer_separation_abs_001",
        "title": "Расслоение слоев при печати ABS",
        "content": """
        Layer separation (расслоение слоев) - это проблема, когда слои не склеиваются между собой.
        
        Основные причины для ABS:
        1. Слишком низкая температура сопла
        2. Сквозняки и перепады температуры
        3. Слишком быстрое охлаждение
        4. Неправильная высота слоя
        
        Решения:
        1. Увеличьте температуру сопла до 240-250°C для ABS
        2. Используйте enclosure (закрытый корпус)
        3. Отключите вентилятор полностью
        4. Уменьшите высоту слоя до 0.2-0.25 мм
        5. Увеличьте температуру стола до 90-100°C
        """,
        "url": "https://3dtoday.ru/test/layer-separation-abs",
        "problem_type": "layer_separation",
        "printer_models": ["Ender-3", "Prusa i3"],
        "materials": ["ABS"],
        "symptoms": ["расслоение слоев", "трещины между слоями", "хрупкость"],
        "solutions": [
            {
                "parameter": "nozzle_temperature",
                "value": 245,
                "unit": "°C",
                "description": "Температура сопла 245°C"
            },
            {
                "parameter": "bed_temperature",
                "value": 95,
                "unit": "°C",
                "description": "Температура стола 95°C"
            },
            {
                "parameter": "fan_speed",
                "value": 0,
                "unit": "%",
                "description": "Отключите вентилятор"
            },
            {
                "parameter": "layer_height",
                "value": 0.2,
                "unit": "mm",
                "description": "Высота слоя 0.2 мм"
            }
        ],
        "section": "Техничка",
        "date": "2024-01-25",
        "relevance_score": 0.90
    }
]


async def test_indexing():
    """Тест индексации статей"""
    print("\n" + "="*60)
    print("🧪 Тест индексации статей в KB")
    print("="*60)
    
    try:
        indexer = get_article_indexer()
        
        print(f"\n📝 Индексация {len(TEST_ARTICLES)} тестовых статей...")
        
        results = await indexer.batch_index_articles(TEST_ARTICLES)
        
        print(f"\n✅ Результаты индексации:")
        print(f"   Всего: {results['total']}")
        print(f"   Успешно: {results['success']}")
        print(f"   Ошибок: {results['failed']}")
        
        if results['errors']:
            print(f"\n⚠️  Ошибки:")
            for error in results['errors']:
                print(f"   - {error['article_id']}: {error['error']}")
        
        return results['success'] == results['total']
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_search():
    """Тест поиска статей"""
    print("\n" + "="*60)
    print("🧪 Тест поиска статей в KB")
    print("="*60)
    
    try:
        rag_service = get_rag_service()
        
        test_queries = [
            {
                "query": "stringing сопли ниточки",
                "filters": None,
                "expected_problem": "stringing"
            },
            {
                "query": "warping коробление PETG",
                "filters": {"material": "PETG"},
                "expected_problem": "warping"
            },
            {
                "query": "расслоение слоев ABS",
                "filters": {"problem_type": "layer_separation"},
                "expected_problem": "layer_separation"
            }
        ]
        
        all_passed = True
        
        for i, test in enumerate(test_queries, 1):
            print(f"\n🔍 Тест {i}: '{test['query']}'")
            
            # Подготовка фильтров
            filters = {}
            if test.get("filters"):
                if "material" in test["filters"]:
                    filters["materials"] = [test["filters"]["material"]]
                if "problem_type" in test["filters"]:
                    filters["problem_type"] = test["filters"]["problem_type"]
            
            # Поиск
            results = await rag_service.hybrid_search(
                query=test["query"],
                filters=filters if filters else None,
                limit=3
            )
            
            if results:
                print(f"   ✅ Найдено статей: {len(results)}")
                for j, result in enumerate(results, 1):
                    print(f"      {j}. {result.get('title', 'Без названия')}")
                    print(f"         Релевантность: {result.get('score', 0):.3f}")
                    print(f"         Проблема: {result.get('problem_type')}")
                
                # Проверка релевантности
                top_result = results[0]
                if top_result.get("problem_type") == test.get("expected_problem"):
                    print(f"   ✅ Релевантность подтверждена")
                else:
                    print(f"   ⚠️  Ожидалась проблема '{test['expected_problem']}', "
                          f"получена '{top_result.get('problem_type')}'")
                    all_passed = False
            else:
                print(f"   ❌ Статьи не найдены")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Главная функция тестирования"""
    print("="*60)
    print("🧪 Тестирование индексации и поиска в KB")
    print("="*60)
    
    # Тест индексации
    indexing_ok = await test_indexing()
    
    if not indexing_ok:
        print("\n❌ Тест индексации не пройден, пропускаем тест поиска")
        return 1
    
    # Небольшая задержка для завершения индексации
    await asyncio.sleep(1)
    
    # Тест поиска
    search_ok = await test_search()
    
    print("\n" + "="*60)
    print("📊 Итоговые результаты:")
    print("="*60)
    print(f"  Индексация: {'✅ PASS' if indexing_ok else '❌ FAIL'}")
    print(f"  Поиск:      {'✅ PASS' if search_ok else '❌ FAIL'}")
    
    all_passed = indexing_ok and search_ok
    
    if all_passed:
        print("\n✅ Все тесты пройдены!")
        return 0
    else:
        print("\n⚠️  Некоторые тесты не пройдены")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


