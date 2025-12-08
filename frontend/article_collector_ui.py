#!/usr/bin/env python3
"""
Streamlit интерфейс для ручного сбора статей в KB
"""

import streamlit as st
import sys
import asyncio
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "app"))

from tools.article_collector import ArticleCollector


# Настройка страницы
st.set_page_config(
    page_title="Сбор статей для KB",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Ручной сбор статей для базы знаний")
st.markdown("---")

# Инициализация коллектора
@st.cache_resource
def get_collector():
    return ArticleCollector()

collector = get_collector()

# Форма ввода статьи
with st.form("article_form"):
    st.subheader("📝 Данные статьи")
    
    col1, col2 = st.columns(2)
    
    with col1:
        url = st.text_input("URL статьи (опционально)", placeholder="https://3dtoday.ru/...")
        section = st.selectbox(
            "Раздел",
            ["Техничка", "3D-печать", "Оборудование", "Материалы", "Применение", "Другое"]
        )
    
    with col2:
        date = st.date_input("Дата публикации (опционально)")
    
    title = st.text_input("Заголовок статьи *", placeholder="Как устранить stringing на Ender-3")
    
    content = st.text_area(
        "Содержимое статьи *",
        height=300,
        placeholder="Вставьте полный текст статьи..."
    )
    
    submitted = st.form_submit_button("🔍 Проверить и добавить в KB", use_container_width=True)

# Обработка формы
if submitted:
    if not title or not content:
        st.error("❌ Заполните обязательные поля: заголовок и содержимое")
    else:
        with st.spinner("🔍 Проверка релевантности статьи..."):
            # Валидация релевантности
            validation = asyncio.run(
                collector.validate_article_relevance(title, content, url)
            )
        
        # Отображение результатов валидации
        st.subheader("📊 Результаты валидации")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            relevance_score = validation.get('relevance_score', 0)
            st.metric(
                "Релевантность",
                f"{relevance_score:.2f}",
                delta=f"{relevance_score - 0.7:.2f}" if relevance_score >= 0.7 else None,
                delta_color="normal" if relevance_score >= 0.7 else "inverse"
            )
        
        with col2:
            quality_score = validation.get('quality_score', 0)
            st.metric(
                "Качество",
                f"{quality_score:.2f}",
                delta=f"{quality_score - 0.6:.2f}" if quality_score >= 0.6 else None,
                delta_color="normal" if quality_score >= 0.6 else "inverse"
            )
        
        with col3:
            has_solutions = validation.get('has_solutions', False)
            st.metric(
                "Есть решения",
                "✅ Да" if has_solutions else "❌ Нет"
            )
        
        # Статус релевантности
        is_relevant = validation.get('is_relevant', False)
        if is_relevant:
            st.success("✅ Статья релевантна и может быть добавлена в KB")
        else:
            st.warning("⚠️ Статья не релевантна. Проверьте критерии ниже.")
        
        # Проблемы и рекомендации
        if validation.get('issues'):
            with st.expander("⚠️ Обнаруженные проблемы"):
                for issue in validation['issues']:
                    st.write(f"- {issue}")
        
        if validation.get('recommendations'):
            with st.expander("💡 Рекомендации"):
                for rec in validation['recommendations']:
                    st.write(f"- {rec}")
        
        # Извлечение метаданных
        if is_relevant:
            with st.spinner("📋 Извлечение метаданных..."):
                metadata = asyncio.run(
                    collector.extract_metadata(title, content)
                )
            
            st.subheader("📝 Извлеченные метаданные")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Тип проблемы:**", metadata.get('problem_type') or "не определен")
                st.write("**Принтеры:**", ', '.join(metadata.get('printer_models', [])) or "не указаны")
                st.write("**Материалы:**", ', '.join(metadata.get('materials', [])) or "не указаны")
            
            with col2:
                st.write("**Симптомы:**", ', '.join(metadata.get('symptoms', [])) or "не указаны")
                st.write("**Количество решений:**", len(metadata.get('solutions', [])))
            
            # Отображение решений
            if metadata.get('solutions'):
                with st.expander("🔧 Извлеченные решения"):
                    for i, solution in enumerate(metadata['solutions'], 1):
                        st.write(f"**Решение {i}:**")
                        st.write(f"- Параметр: {solution.get('parameter', 'N/A')}")
                        st.write(f"- Значение: {solution.get('value', 'N/A')} {solution.get('unit', '')}")
                        st.write(f"- Описание: {solution.get('description', 'N/A')}")
                        st.write("---")
            
            # Подтверждение и индексация
            st.markdown("---")
            
            if st.button("💾 Добавить статью в KB", type="primary", use_container_width=True):
                with st.spinner("💾 Индексация статьи..."):
                    result = asyncio.run(
                        collector.process_and_index_article(
                            title, content, url, section
                        )
                    )
                
                if result["success"]:
                    st.success(f"✅ Статья успешно добавлена в KB!")
                    st.info(f"**ID статьи:** `{result['article_id']}`")
                    
                    # Очистка формы
                    st.rerun()
                else:
                    st.error(f"❌ Ошибка: {result.get('error')}")

# Боковая панель с инструкциями
with st.sidebar:
    st.header("📖 Инструкция")
    st.markdown("""
    ### Процесс добавления статьи:
    
    1. **Введите данные статьи**
       - URL (опционально)
       - Заголовок (обязательно)
       - Содержимое (обязательно)
    
    2. **Проверка релевантности**
       - Система автоматически проверит релевантность
       - Оценка релевантности (0.0-1.0)
       - Оценка качества (0.0-1.0)
       - Проверка наличия решений
    
    3. **Извлечение метаданных**
       - Тип проблемы
       - Модели принтеров
       - Материалы
       - Симптомы
       - Решения с параметрами
    
    4. **Индексация**
       - Статья добавляется в Qdrant
       - Генерируются эмбеддинги
       - Статья доступна для поиска
    
    ### Критерии качества:
    
    ✅ **Хорошая статья:**
    - Содержит конкретные решения
    - Упоминает модели принтеров/материалы
    - Имеет четкую структуру
    - Актуальная информация
    
    ❌ **Плохая статья:**
    - Общие рассуждения
    - Нет конкретных решений
    - Устаревшая информация
    """)
    
    st.markdown("---")
    st.subheader("📊 Статистика KB")
    
    # Здесь можно добавить статистику из KB
    st.info("Статистика будет отображаться здесь")



