"""
Streamlit интерфейс для пользователей (диагностика проблем)
Работает через FastAPI
"""

import streamlit as st
import httpx
from typing import List, Dict, Any, Optional
import json

# Конфигурация API
API_BASE_URL = "http://localhost:8000"

# Настройка страницы
st.set_page_config(
    page_title="Диагностика проблем 3D-печати",
    page_icon="🔧",
    layout="wide"
)

st.title("🔧 Диагностика проблем 3D-печати")
st.markdown("---")

# Инициализация session state для истории диалога
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

if "user_context" not in st.session_state:
    st.session_state.user_context = {
        "printer_model": None,
        "material": None,
        "problem_type": None
    }

# Боковая панель с контекстом пользователя
with st.sidebar:
    st.header("⚙️ Контекст")
    
    st.subheader("Информация о вашем принтере")
    
    printer_model = st.text_input(
        "Модель принтера",
        value=st.session_state.user_context.get("printer_model", ""),
        placeholder="Ender-3, Anycubic Kobra, etc."
    )
    
    material = st.selectbox(
        "Материал",
        ["", "PLA", "PETG", "ABS", "TPU", "Другое"],
        index=0 if not st.session_state.user_context.get("material") else 
              ["PLA", "PETG", "ABS", "TPU", "Другое"].index(st.session_state.user_context.get("material")) + 1
    )
    
    # Обновление контекста
    if printer_model:
        st.session_state.user_context["printer_model"] = printer_model
    if material:
        st.session_state.user_context["material"] = material
    
    st.markdown("---")
    
    if st.button("🗑️ Очистить историю"):
        st.session_state.conversation_history = []
        st.session_state.user_context = {
            "printer_model": None,
            "material": None,
            "problem_type": None
        }
        st.rerun()
    
    st.markdown("---")
    st.info("💡 Опишите проблему подробно для лучшей диагностики")

# Основной интерфейс
st.subheader("💬 Опишите вашу проблему")

# Отображение истории диалога
if st.session_state.conversation_history:
    st.markdown("### История диалога")
    for i, message in enumerate(st.session_state.conversation_history):
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
        else:
            with st.chat_message("assistant"):
                st.write(message["content"])
                
                # Отображение уточняющих вопросов, если есть
                if message.get("clarification_questions"):
                    st.markdown("**❓ Уточняющие вопросы:**")
                    for q in message["clarification_questions"]:
                        st.write(f"- {q['question']}")
    
    st.markdown("---")

# Форма для нового запроса
with st.form("diagnostic_form", clear_on_submit=False):
    query = st.text_area(
        "Опишите проблему",
        height=150,
        placeholder="Например: У меня появляются ниточки между деталями при печати PLA на Ender-3..."
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        upload_image = st.file_uploader(
            "Загрузить фото дефекта (опционально)",
            type=['png', 'jpg', 'jpeg'],
            help="Загрузка изображений будет доступна после реализации Vision Agent"
        )
    
    with col2:
        st.info("📸 Анализ изображений будет доступен в следующей версии")
    
    submitted = st.form_submit_button("🔍 Получить диагностику", use_container_width=True)

# Обработка запроса
if submitted and query:
    # Добавление запроса в историю
    st.session_state.conversation_history.append({
        "role": "user",
        "content": query
    })
    
    # Подготовка запроса к API
    with st.spinner("🔍 Анализ проблемы и поиск решений..."):
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{API_BASE_URL}/api/diagnose",
                    json={
                        "query": query,
                        "printer_model": st.session_state.user_context.get("printer_model"),
                        "material": st.session_state.user_context.get("material"),
                        "problem_type": st.session_state.user_context.get("problem_type"),
                        "conversation_history": st.session_state.conversation_history[:-1]  # Без текущего запроса
                    }
                )
                
                if response.status_code == 200:
                    diagnostic = response.json()
                else:
                    st.error(f"❌ Ошибка: {response.text}")
                    st.stop()
        except Exception as e:
            st.error(f"❌ Ошибка подключения к API: {e}")
            st.info("💡 Убедитесь, что FastAPI сервер запущен: `uvicorn backend.app.main:app --reload`")
            st.stop()
    
    # Отображение ответа
    with st.chat_message("assistant"):
        st.write(diagnostic.get("answer", "Не удалось получить ответ"))
        
        # Отображение уверенности
        confidence = diagnostic.get("confidence", 0.0)
        if confidence < 0.7:
            st.warning(f"⚠️ Уверенность в ответе: {confidence:.0%}. Могут потребоваться уточнения.")
        
        # Уточняющие вопросы
        if diagnostic.get("needs_clarification") and diagnostic.get("clarification_questions"):
            st.markdown("---")
            st.markdown("### ❓ Нужны уточнения")
            
            for i, question in enumerate(diagnostic["clarification_questions"]):
                st.markdown(f"**{i+1}. {question['question']}**")
                
                if question.get("options"):
                    selected = st.radio(
                        f"Выберите вариант:",
                        question["options"],
                        key=f"clarification_{i}",
                        horizontal=True
                    )
                    
                    # Сохранение ответа в контекст
                    if question["question_type"] == "printer_model":
                        st.session_state.user_context["printer_model"] = selected
                    elif question["question_type"] == "material":
                        st.session_state.user_context["material"] = selected
        
        # Релевантные статьи
        if diagnostic.get("relevant_articles"):
            st.markdown("---")
            st.markdown("### 📚 Релевантные статьи из базы знаний")
            
            for article in diagnostic["relevant_articles"]:
                with st.expander(f"📄 {article.get('title', 'Без названия')} (релевантность: {article.get('score', 0):.2f})"):
                    if article.get("url"):
                        st.markdown(f"🔗 [Открыть статью]({article['url']})")
        
        # Добавление ответа в историю
        st.session_state.conversation_history.append({
            "role": "assistant",
            "content": diagnostic.get("answer", ""),
            "clarification_questions": diagnostic.get("clarification_questions"),
            "relevant_articles": diagnostic.get("relevant_articles")
        })
    
    # Автоматический rerun для обновления интерфейса
    st.rerun()

# Инструкция
with st.expander("📖 Как пользоваться"):
    st.markdown("""
    ### Процесс диагностики:
    
    1. **Опишите проблему**
       - Чем подробнее, тем лучше
       - Укажите симптомы (ниточки, отслоение, трещины)
       - Если знаете - укажите модель принтера и материал
    
    2. **Получите диагностику**
       - Система найдет релевантные статьи в базе знаний
       - Даст конкретные рекомендации с параметрами
       - Может задать уточняющие вопросы
    
    3. **Ответьте на уточняющие вопросы**
       - Это поможет улучшить точность диагностики
       - Система запомнит ваш принтер и материал
    
    4. **Следуйте рекомендациям**
       - Рекомендации основаны на проверенных статьях
       - Параметры (температура, скорость) указаны конкретно
    
    ### Примеры запросов:
    
    - "У меня появляются ниточки между деталями при печати PLA"
    - "Печать отслаивается от стола на Ender-3"
    - "Трещины в слоях при печати PETG"
    - "Недозаполнение при печати ABS"
    
    ### Советы:
    
    💡 **Укажите контекст в боковой панели** - модель принтера и материал
    💡 **Приложите фото** - поможет точнее определить проблему (скоро будет доступно)
    💡 **Будьте конкретны** - чем подробнее описание, тем точнее диагностика
    """)


