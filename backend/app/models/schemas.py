"""
Pydantic модели для API запросов и ответов
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ArticleInput(BaseModel):
    """Модель для добавления статьи"""
    title: str = Field(..., description="Заголовок статьи")
    content: str = Field(..., description="Содержимое статьи")
    url: Optional[str] = Field(None, description="URL статьи")
    section: Optional[str] = Field(None, description="Раздел (Техничка, 3D-печать, etc.)")


class DiagnosticRequest(BaseModel):
    """Модель для запроса диагностики"""
    query: str = Field(..., description="Текст запроса пользователя")
    printer_model: Optional[str] = Field(None, description="Модель принтера")
    material: Optional[str] = Field(None, description="Материал (PLA, PETG, etc.)")
    problem_type: Optional[str] = Field(None, description="Тип проблемы")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default_factory=list,
        description="История диалога"
    )


class ClarificationQuestion(BaseModel):
    """Модель уточняющего вопроса"""
    question: str = Field(..., description="Текст вопроса")
    question_type: str = Field(..., description="Тип вопроса (printer_model, material, symptom, etc.)")
    options: Optional[List[str]] = Field(None, description="Варианты ответов (если есть)")


class DiagnosticResponse(BaseModel):
    """Модель ответа диагностики"""
    answer: str = Field(..., description="Ответ системы")
    needs_clarification: bool = Field(..., description="Нужны ли уточнения")
    clarification_questions: Optional[List[ClarificationQuestion]] = Field(
        None,
        description="Уточняющие вопросы"
    )
    relevant_articles: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Релевантные статьи из KB"
    )
    confidence: float = Field(..., description="Уверенность в ответе (0.0-1.0)")


class ValidationResponse(BaseModel):
    """Модель ответа валидации статьи"""
    is_relevant: bool = Field(..., description="Релевантна ли статья")
    relevance_score: float = Field(..., description="Оценка релевантности")
    quality_score: float = Field(..., description="Оценка качества")
    has_solutions: bool = Field(..., description="Есть ли решения")
    issues: List[str] = Field(default_factory=list, description="Проблемы")
    recommendations: List[str] = Field(default_factory=list, description="Рекомендации")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Извлеченные метаданные")


class AddFromParseRequest(BaseModel):
    """Модель для добавления статьи из результата парсинга"""
    parsed_document: Dict[str, Any] = Field(..., description="Распарсенный документ")
    review: Dict[str, Any] = Field(..., description="Результат анализа библиотекарем")
    admin_decision: str = Field(..., description="Решение администратора (approve/reject/needs_review)")
    relevance_threshold: float = Field(0.6, description="Порог релевантности, установленный администратором")


