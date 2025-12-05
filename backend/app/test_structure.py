#!/usr/bin/env python3
"""
Тест структуры проекта - проверка импортов и структуры директорий
"""

import sys
from pathlib import Path

def test_structure():
    """Проверка структуры проекта"""
    errors = []
    warnings = []
    
    # Проверка директорий
    required_dirs = [
        "backend/app",
        "backend/app/mcp",
        "backend/app/agents",
        "backend/app/services",
        "backend/app/models",
        "frontend",
        "knowledge_base/articles",
        "knowledge_base/examples"
    ]
    
    print("🔍 Проверка структуры директорий...")
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"  ✅ {dir_path}")
        else:
            errors.append(f"Отсутствует директория: {dir_path}")
            print(f"  ❌ {dir_path}")
    
    # Проверка файлов
    required_files = [
        "backend/requirements.txt",
        "config.env",
        ".gitignore",
        "README.md"
    ]
    
    print("\n🔍 Проверка файлов...")
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            warnings.append(f"Отсутствует файл: {file_path}")
            print(f"  ⚠️  {file_path}")
    
    # Проверка __init__.py
    init_files = [
        "backend/app/__init__.py",
        "backend/app/mcp/__init__.py",
        "backend/app/agents/__init__.py",
        "backend/app/services/__init__.py",
        "backend/app/models/__init__.py"
    ]
    
    print("\n🔍 Проверка __init__.py...")
    for init_file in init_files:
        if Path(init_file).exists():
            print(f"  ✅ {init_file}")
        else:
            errors.append(f"Отсутствует файл: {init_file}")
            print(f"  ❌ {init_file}")
    
    # Итоги
    print("\n" + "="*50)
    if errors:
        print(f"❌ Найдено ошибок: {len(errors)}")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("✅ Структура проекта корректна!")
        if warnings:
            print(f"\n⚠️  Предупреждений: {len(warnings)}")
            for warning in warnings:
                print(f"  - {warning}")
        return True

if __name__ == "__main__":
    # Переходим в корень проекта
    project_root = Path(__file__).resolve().parents[2]
    import os
    os.chdir(project_root)
    
    success = test_structure()
    sys.exit(0 if success else 1)

