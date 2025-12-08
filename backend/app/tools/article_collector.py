#!/usr/bin/env python3
"""
Инструмент для ручного сбора и валидации статей
"""

import sys
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.llm_client import get_llm_client
from services.article_indexer import get_article_indexer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArticleCollector:
    """
    Инструмент для ручного сбора и валидации статей
    """
    
    def __init__(self):
        self.llm_client = get_llm_client()
        self.indexer = get_article_indexer()
    
    async def validate_article_relevance(
        self,
        title: str,
        content: str,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Проверка релевантности статьи через LLM
        
        Returns:
            {
                "relevance_score": float,
                "quality_score": float,
                "has_solutions": bool,
                "is_relevant": bool,
                "issues": List[str],
                "recommendations": List[str]
            }
        """
        prompt = f"""Проверь релевантность статьи для системы диагностики проблем 3D-печати.

ЗАГОЛОВОК: {title}
URL: {url or "не указан"}

СОДЕРЖАНИЕ:
{content[:3000]}

КРИТЕРИИ РЕЛЕВАНТНОСТИ:
1. Содержит ли статья информацию о проблемах 3D-печати?
2. Есть ли конкретные решения или настройки с параметрами?
3. Упоминаются ли модели принтеров, материалы, параметры (температура, скорость, retraction)?
4. Является ли информация полезной для диагностики?

КРИТЕРИИ КАЧЕСТВА:
1. Структурированность (есть ли четкая структура?)
2. Конкретность (есть ли конкретные параметры, значения?)
3. Полнота (достаточно ли информации?)
4. Актуальность (не устарела ли информация?)

ПРОВЕРКА РЕШЕНИЙ:
Есть ли в статье конкретные решения с параметрами? (температура, скорость, retraction, мм, °C, mm/s)

Верни ТОЛЬКО валидный JSON без дополнительного текста:
{{
    "relevance_score": 0.0-1.0,
    "quality_score": 0.0-1.0,
    "has_solutions": true/false,
    "is_relevant": true/false,
    "issues": ["проблема1", "проблема2"],
    "recommendations": ["рекомендация1"]
}}
"""
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt="Ты эксперт по оценке качества технических статей о 3D-печати. Отвечай только валидным JSON."
            )
            
            # Извлечение JSON из ответа
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
            else:
                # Fallback: простая проверка по ключевым словам
                result = self._simple_relevance_check(title, content)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка валидации через LLM: {e}")
            # Fallback на простую проверку
            return self._simple_relevance_check(title, content)
    
    def _simple_relevance_check(self, title: str, content: str) -> Dict[str, Any]:
        """Простая проверка релевантности по ключевым словам"""
        content_lower = content.lower()
        title_lower = title.lower()
        
        # Ключевые слова проблем
        problem_keywords = [
            "stringing", "warping", "layer", "сопли", "ниточки",
            "отслоение", "трещины", "дефект", "проблема"
        ]
        
        # Ключевые слова решений
        solution_keywords = [
            "температура", "скорость", "retraction", "fan", "вентилятор",
            "мм", "°c", "mm/s", "процент", "увеличьте", "уменьшите"
        ]
        
        # Ключевые слова оборудования
        equipment_keywords = [
            "принтер", "printer", "ender", "anycubic", "pla", "petg", "abs"
        ]
        
        has_problems = sum(1 for kw in problem_keywords if kw in content_lower or kw in title_lower)
        has_solutions = sum(1 for kw in solution_keywords if kw in content_lower)
        has_equipment = sum(1 for kw in equipment_keywords if kw in content_lower or kw in title_lower)
        
        # Простая оценка
        relevance_score = min(0.3 + (has_problems * 0.2) + (has_solutions * 0.3) + (has_equipment * 0.2), 1.0)
        quality_score = min(0.4 + (has_solutions * 0.3) + (len(content) > 500) * 0.3, 1.0)
        has_solutions_bool = has_solutions >= 3
        
        return {
            "relevance_score": round(relevance_score, 2),
            "quality_score": round(quality_score, 2),
            "has_solutions": has_solutions_bool,
            "is_relevant": relevance_score >= 0.6 and has_solutions_bool,
            "issues": [] if has_solutions_bool else ["Недостаточно конкретных решений"],
            "recommendations": []
        }
    
    async def extract_metadata(
        self,
        title: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Извлечение метаданных из статьи через LLM
        
        Returns:
            {
                "problem_type": str,
                "printer_models": List[str],
                "materials": List[str],
                "symptoms": List[str],
                "solutions": List[Dict]
            }
        """
        prompt = f"""Извлеки структурированные метаданные из статьи о 3D-печати.

ЗАГОЛОВОК: {title}
СОДЕРЖАНИЕ:
{content[:3000]}

ИЗВЛЕКИ:
1. Тип проблемы (problem_type): stringing, warping, layer_separation, bed_adhesion, overhang, underextrusion, overextrusion, или null
2. Модели принтеров (printer_models): ["Ender-3", "Anycubic Kobra", ...] или []
3. Материалы (materials): ["PLA", "PETG", "ABS", ...] или []
4. Симптомы (symptoms): ["ниточки", "отслоение", ...] или []
5. Решения (solutions): [{{"parameter": "retraction_length", "value": 6, "unit": "mm", "description": "..."}}] или []

ВАЖНО:
- Используй ТОЛЬКО информацию из статьи
- Не выдумывай, если информации нет - укажи null или []
- Будь точным в значениях параметров

Верни ТОЛЬКО валидный JSON без дополнительного текста:
{{
    "problem_type": "stringing" или null,
    "printer_models": ["Ender-3"] или [],
    "materials": ["PLA"] или [],
    "symptoms": ["ниточки"] или [],
    "solutions": [
        {{
            "parameter": "retraction_length",
            "value": 6,
            "unit": "mm",
            "description": "Увеличьте retraction до 6 мм"
        }}
    ] или []
}}
"""
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt="Ты эксперт по извлечению структурированных данных из технических статей. Отвечай только валидным JSON."
            )
            
            # Извлечение JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                metadata = json.loads(json_str)
            else:
                metadata = {
                    "problem_type": None,
                    "printer_models": [],
                    "materials": [],
                    "symptoms": [],
                    "solutions": []
                }
            
            return metadata
            
        except Exception as e:
            logger.error(f"Ошибка извлечения метаданных: {e}")
            return {
                "problem_type": None,
                "printer_models": [],
                "materials": [],
                "symptoms": [],
                "solutions": []
            }
    
    async def process_and_index_article(
        self,
        title: str,
        content: str,
        url: Optional[str] = None,
        section: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Полный процесс: валидация → извлечение метаданных → индексация
        
        Returns:
            {
                "success": bool,
                "article_id": str,
                "validation": dict,
                "metadata": dict,
                "error": str (если success=False)
            }
        """
        # 1. Валидация релевантности
        validation = await self.validate_article_relevance(title, content, url)
        
        if not validation.get("is_relevant", False):
            return {
                "success": False,
                "error": f"Статья не релевантна (relevance_score: {validation.get('relevance_score', 0):.2f})",
                "validation": validation
            }
        
        # 2. Извлечение метаданных
        metadata = await self.extract_metadata(title, content)
        
        if not metadata.get("problem_type"):
            return {
                "success": False,
                "error": "Не удалось определить тип проблемы",
                "validation": validation,
                "metadata": metadata
            }
        
        # 3. Подготовка статьи для индексации
        article_id = f"{metadata['problem_type']}_{hash(title) % 10000}"
        
        article = {
            "article_id": article_id,
            "title": title,
            "content": content,
            "url": url or "",
            "section": section or "unknown",
            "date": "",
            "relevance_score": validation.get("relevance_score", 0.0),
            "problem_type": metadata.get("problem_type"),
            "printer_models": metadata.get("printer_models", []),
            "materials": metadata.get("materials", []),
            "symptoms": metadata.get("symptoms", []),
            "solutions": metadata.get("solutions", [])
        }
        
        # 4. Индексация
        result = await self.indexer.index_article(article)
        
        if result["success"]:
            return {
                "success": True,
                "article_id": article_id,
                "validation": validation,
                "metadata": metadata
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Ошибка индексации"),
                "validation": validation,
                "metadata": metadata
            }


async def main():
    """Интерактивный режим для ручного сбора статей"""
    print("="*60)
    print("📚 Инструмент для ручного сбора статей в KB")
    print("="*60)
    
    collector = ArticleCollector()
    
    while True:
        print("\n" + "-"*60)
        print("Введите данные статьи (или 'exit' для выхода):")
        
        url = input("URL статьи (опционально): ").strip()
        if url.lower() == 'exit':
            break
        
        title = input("Заголовок: ").strip()
        if not title:
            print("❌ Заголовок обязателен")
            continue
        
        print("Содержимое (введите 'END' на новой строке для завершения):")
        content_lines = []
        while True:
            line = input()
            if line.strip() == 'END':
                break
            content_lines.append(line)
        
        content = '\n'.join(content_lines)
        if not content:
            print("❌ Содержимое обязательно")
            continue
        
        # Валидация
        print("\n🔍 Проверка релевантности...")
        validation = await collector.validate_article_relevance(title, content, url)
        
        print(f"\n📊 Результаты валидации:")
        print(f"   Релевантность: {validation.get('relevance_score', 0):.2f}")
        print(f"   Качество: {validation.get('quality_score', 0):.2f}")
        print(f"   Есть решения: {'✅' if validation.get('has_solutions') else '❌'}")
        print(f"   Релевантна: {'✅' if validation.get('is_relevant') else '❌'}")
        
        if validation.get('issues'):
            print(f"   Проблемы: {', '.join(validation['issues'])}")
        
        if not validation.get("is_relevant"):
            print("\n⚠️  Статья не релевантна. Продолжить? (y/n): ", end='')
            if input().lower() != 'y':
                continue
        
        # Извлечение метаданных
        print("\n📋 Извлечение метаданных...")
        metadata = await collector.extract_metadata(title, content)
        
        print(f"\n📝 Извлеченные метаданные:")
        print(f"   Тип проблемы: {metadata.get('problem_type') or 'не определен'}")
        print(f"   Принтеры: {', '.join(metadata.get('printer_models', [])) or 'не указаны'}")
        print(f"   Материалы: {', '.join(metadata.get('materials', [])) or 'не указаны'}")
        print(f"   Симптомы: {', '.join(metadata.get('symptoms', [])) or 'не указаны'}")
        print(f"   Решений: {len(metadata.get('solutions', []))}")
        
        # Подтверждение индексации
        print("\n💾 Добавить статью в KB? (y/n): ", end='')
        if input().lower() != 'y':
            continue
        
        # Индексация
        print("\n💾 Индексация статьи...")
        result = await collector.process_and_index_article(title, content, url)
        
        if result["success"]:
            print(f"\n✅ Статья успешно добавлена в KB!")
            print(f"   ID: {result['article_id']}")
        else:
            print(f"\n❌ Ошибка: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())



