#!/usr/bin/env python3
"""
Прямое тестирование небольшого количества источников через сервисы проекта
(без API, напрямую через Python модули)
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Тестовые источники (небольшое количество)
TEST_SOURCES = [
    {
        "url": "https://www.simplify3d.com/resources/print-quality-troubleshooting/stringing-or-oozing/",
        "description": "Simplify3D - Stringing (лучший пример с изображениями)",
        "provider": "gemini",
        "has_images": True
    },
    {
        "url": "https://all3dp.com/2/3d-printing-warping-how-to-fix-it/",
        "description": "All3DP - Warping",
        "provider": "ollama",
        "has_images": True
    }
]


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
def print_header(msg): print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}\n{Colors.BOLD}{msg}{Colors.END}\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}\n")


async def test_source(source: dict, index: int):
    """Тест одного источника"""
    print_header(f"Тест {index}: {source['description']}")
    print_info(f"URL: {source['url']}")
    print_info(f"Провайдер: {source['provider']}")
    
    try:
        # Импортируем сервисы
        from backend.app.services.document_parser import DocumentParser
        from backend.app.agents.kb_librarian import KBLibrarianAgent
        
        # ФАЗА 1: Парсинг
        print_info("\n📋 ФАЗА 1: ПАРСИНГ")
        parser = DocumentParser()
        doc_data = await parser.parse_document(source['url'], "url")
        
        if not doc_data:
            print_error("Парсинг не удался")
            return {"success": False, "error": "Parsing failed"}
        
        print_success("✅ Парсинг успешен")
        print_info(f"   Заголовок: {doc_data.get('title', 'N/A')[:80]}")
        print_info(f"   Размер контента: {len(doc_data.get('content', ''))} символов")
        
        images = doc_data.get("images", [])
        if images:
            print_success(f"   Изображений найдено: {len(images)}")
        else:
            print_info("   Изображения не найдены")
        
        # ФАЗА 2: Анализ релевантности
        print_info("\n📋 ФАЗА 2: АНАЛИЗ РЕЛЕВАНТНОСТИ")
        librarian = KBLibrarianAgent(llm_provider=source['provider'])
        
        review_result = await librarian.review_and_decide(
            title=doc_data["title"],
            content=doc_data["content"],
            images=images,
            url=doc_data.get("url"),
            content_type=doc_data.get("content_type")
        )
        
        relevance_score = review_result.get("relevance_score", 0.0)
        is_relevant = review_result.get("is_relevant", False)
        decision = review_result.get("decision", "needs_review")
        
        print_info(f"   Релевантность: {relevance_score:.2f}")
        print_info(f"   Релевантна: {'✅ Да' if is_relevant else '❌ Нет'}")
        print_info(f"   Решение: {decision}")
        
        if relevance_score >= 0.7:
            print_success("   ✅ Релевантность >= 0.7 (одобрено)")
        elif relevance_score >= 0.6:
            print_warning("   ⚠️  Релевантность 0.6-0.7 (требуется проверка)")
        else:
            print_error("   ❌ Релевантность < 0.6 (отклонено)")
        
        # Проверка абстрактов изображений (для Gemini)
        if source['provider'] == 'gemini' and images:
            image_analysis = review_result.get("summary", {}).get("visual_indicators", [])
            if image_analysis:
                print_success(f"   ✅ Изображения проанализированы: {len(image_analysis)} релевантных")
                problems_shown = review_result.get("summary", {}).get("problems_shown", [])
                if problems_shown:
                    print_success(f"   ✅ Проблемы из изображений: {', '.join(problems_shown)}")
        
        abstract = review_result.get("abstract", "")
        if abstract:
            print_success(f"   ✅ Abstract создан: {abstract[:150]}...")
        
        # ФАЗА 3: Размещение в KB (опционально)
        print_info("\n📋 ФАЗА 3: РАЗМЕЩЕНИЕ В KB")
        print_warning("   Пропущено (используйте --add для добавления в KB)")
        
        return {
            "success": True,
            "provider": source['provider'],
            "relevance_score": relevance_score,
            "is_relevant": is_relevant,
            "decision": decision,
            "images_count": len(images),
            "has_abstract": bool(abstract)
        }
        
    except Exception as e:
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


async def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Прямое тестирование источников")
    parser.add_argument("--add", action="store_true", help="Добавлять в KB")
    parser.add_argument("--source", type=int, help="Тестировать только один источник (номер)")
    
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("=" * 70)
    print("🧪 Прямое тестирование небольшого количества источников")
    print("=" * 70)
    print(f"{Colors.END}\n")
    
    print_info(f"Выбрано источников: {len(TEST_SOURCES)}")
    print_info("Тестируем все три фазы: парсинг → релевантность → размещение\n")
    
    results = []
    
    sources_to_test = TEST_SOURCES
    if args.source:
        if 1 <= args.source <= len(TEST_SOURCES):
            sources_to_test = [TEST_SOURCES[args.source - 1]]
        else:
            print_error(f"Неверный номер источника. Доступно: 1-{len(TEST_SOURCES)}")
            return 1
    
    for i, source in enumerate(sources_to_test, 1):
        result = await test_source(source, i)
        results.append(result)
        print()
    
    # Итоги
    print(f"{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}📊 Итоги тестирования{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")
    
    for i, result in enumerate(results, 1):
        if result.get("success"):
            provider = result.get("provider", "unknown")
            relevance = result.get("relevance_score", "N/A")
            images = result.get("images_count", 0)
            print_success(f"Источник {i} ({provider}): ПРОЙДЕН (relevance={relevance}, images={images})")
        else:
            print_error(f"Источник {i}: ПРОВАЛЕН - {result.get('error', 'Unknown')}")
    
    passed = sum(1 for r in results if r.get("success"))
    total = len(results)
    
    print(f"\n{Colors.BOLD}Всего тестов: {total}{Colors.END}")
    print(f"{Colors.GREEN if passed == total else Colors.YELLOW}Пройдено: {passed}/{total}{Colors.END}")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


