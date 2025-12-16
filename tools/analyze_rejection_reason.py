#!/usr/bin/env python3
"""
Анализ причины отклонения документа LLM
Проверяет логику принятия решений в KBLibrarianAgent
"""

import sys
import json
from pathlib import Path

def analyze_decision_logic():
    """Анализ логики принятия решений"""
    
    print("=" * 70)
    print("🔍 Анализ логики принятия решений в KBLibrarianAgent")
    print("=" * 70 + "\n")
    
    # Симуляция данных из теста PDF
    relevance_score = 0.95
    quality_score = 0.90
    is_relevant = False  # Это значение вернула Gemini3
    has_valuable_info = True  # Предполагаем
    is_duplicate = False
    
    print("📊 Данные из анализа PDF:")
    print(f"  relevance_score: {relevance_score}")
    print(f"  quality_score: {quality_score}")
    print(f"  is_relevant: {is_relevant}")
    print(f"  has_valuable_info: {has_valuable_info}")
    print(f"  is_duplicate: {is_duplicate}\n")
    
    print("🔍 Логика _make_decision (строки 470-526):\n")
    
    # Проверка 1: Дубликат
    print("1️⃣ Проверка дубликата (строка 486):")
    if is_duplicate:
        print("   ❌ REJECT: Документ является дубликатом")
        return
    print("   ✅ Не дубликат, продолжаем\n")
    
    # Проверка 2: Релевантность
    print("2️⃣ Проверка релевантности (строка 496):")
    print(f"   Условие: not is_relevant ({not is_relevant}) OR relevance_score < 0.6 ({relevance_score < 0.6})")
    if not is_relevant or relevance_score < 0.6:
        print(f"   ❌ REJECT: Документ не релевантен (is_relevant={is_relevant}, score={relevance_score:.2f})")
        print("   ⚠️  ПРОБЛЕМА: Эта проверка ДОЛЖНА была вернуть REJECT!")
        print("   ⚠️  Но в тесте вернулось APPROVE - это баг в логике!")
        return
    print("   ✅ Релевантен, продолжаем\n")
    
    # Проверка 3: Ценная информация
    print("3️⃣ Проверка ценной информации (строка 503):")
    if not has_valuable_info or quality_score < 0.6:
        print(f"   ❌ REJECT: Нет ценной информации")
        return
    print("   ✅ Есть ценная информация, продолжаем\n")
    
    # Проверка 4: Одобрение
    print("4️⃣ Проверка одобрения (строка 510):")
    print(f"   Условие: relevance_score >= 0.7 ({relevance_score >= 0.7}) AND quality_score >= 0.7 ({quality_score >= 0.7}) AND not is_duplicate ({not is_duplicate})")
    if relevance_score >= 0.7 and quality_score >= 0.7 and not is_duplicate:
        print("   ✅ APPROVE: Документ релевантен и качественен")
        print("   ⚠️  ПРОБЛЕМА: Эта проверка НЕ учитывает is_relevant!")
        print("   ⚠️  Она проверяет только relevance_score >= 0.7, но не is_relevant!")
        return
    print("   ⚠️  NEEDS_REVIEW: Требуется проверка\n")
    
    print("\n" + "=" * 70)
    print("🎯 ВЫВОДЫ:")
    print("=" * 70)
    print("\n❌ ПРОБЛЕМА В ЛОГИКЕ:")
    print("   1. Строка 496 должна была вернуть REJECT при is_relevant=False")
    print("   2. Но почему-то код дошел до строки 510 и вернул APPROVE")
    print("   3. Это означает, что либо:")
    print("      a) is_relevant был True в момент проверки (но Gemini3 вернула False)")
    print("      b) Есть баг в логике - проверка на строке 496 не сработала")
    print("      c) Логика была изменена и не учитывает is_relevant при approve")
    print("\n💡 РЕШЕНИЕ:")
    print("   Нужно исправить строку 510, чтобы она проверяла is_relevant:")
    print("   if relevance_score >= 0.7 and quality_score >= 0.7 and is_relevant and not is_duplicate:")


if __name__ == "__main__":
    analyze_decision_logic()


