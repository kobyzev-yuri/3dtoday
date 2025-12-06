#!/usr/bin/env python3
"""
Скрипт для просмотра статьи из KB с правильной кодировкой UTF-8
"""

import httpx
import json
import sys
from pathlib import Path

def view_article(article_id: str):
    """Просмотр статьи по ID"""
    try:
        response = httpx.get(f"http://localhost:8000/api/kb/articles/{article_id}", timeout=10)
        response.raise_for_status()
        article = response.json()
        
        print(f"📄 Статья: {article.get('title', 'N/A')}")
        print("=" * 60)
        print(f"ID: {article.get('article_id', 'N/A')}")
        print(f"Раздел: {article.get('section', 'N/A')}")
        print(f"Тип проблемы: {article.get('problem_type', 'N/A')}")
        print(f"Принтеры: {', '.join(article.get('printer_models', []))}")
        print(f"Материалы: {', '.join(article.get('materials', []))}")
        print()
        
        print("📝 Содержимое:")
        print(article.get('content', '')[:500] + "..." if len(article.get('content', '')) > 500 else article.get('content', ''))
        print()
        
        solutions = article.get('solutions', [])
        if solutions:
            print("🔧 Решения:")
            for i, sol in enumerate(solutions, 1):
                print(f"\n{i}. {sol.get('parameter', 'N/A')}: {sol.get('value', 'N/A')} {sol.get('unit', '')}")
                print(f"   Описание: {sol.get('description', 'N/A')}")
        
        return 0
        
    except httpx.ConnectError:
        print("❌ Ошибка: FastAPI не запущен")
        print("💡 Запустите: ./scripts/start_fastapi.sh")
        return 1
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"❌ Статья с ID '{article_id}' не найдена")
        else:
            print(f"❌ HTTP ошибка: {e.response.status_code}")
        return 1
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

def list_articles(limit: int = 10):
    """Список статей"""
    try:
        response = httpx.get(f"http://localhost:8000/api/kb/articles?limit={limit}", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"📊 Статьи в KB (всего: {data.get('total', 0)})")
        print("=" * 60)
        
        for i, article in enumerate(data.get('articles', []), 1):
            print(f"\n{i}. {article.get('title', 'N/A')}")
            print(f"   ID: {article.get('article_id', 'N/A')}")
            print(f"   Раздел: {article.get('section', 'N/A')}")
            if article.get('problem_type'):
                print(f"   Проблема: {article.get('problem_type')}")
        
        return 0
        
    except httpx.ConnectError:
        print("❌ Ошибка: FastAPI не запущен")
        return 1
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print(f"  {sys.argv[0]} <article_id>  - просмотр статьи")
        print(f"  {sys.argv[0]} list          - список статей")
        print(f"  {sys.argv[0]} list <limit>  - список статей (с лимитом)")
        return 1
    
    if sys.argv[1] == "list":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        return list_articles(limit)
    else:
        article_id = sys.argv[1]
        return view_article(article_id)

if __name__ == "__main__":
    sys.exit(main())

