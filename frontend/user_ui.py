"""
Streamlit интерфейс для пользователей (диагностика проблем)
Работает через FastAPI
"""

import streamlit as st
import httpx
from typing import List, Dict, Any, Optional
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / "config.env")

# Конфигурация API
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Таймаут для диагностики (может занимать много времени из-за LLM)
DIAGNOSTIC_TIMEOUT = float(os.getenv("DIAGNOSTIC_TIMEOUT", os.getenv("API_REQUEST_TIMEOUT", "300")))  # По умолчанию 5 минут

# Настройка страницы
st.set_page_config(
    page_title="Диагностика проблем 3D-печати",
    page_icon="🔧",
    layout="wide"
)

st.title("🔧 Диагностика проблем 3D-печати")
st.markdown("---")

# Проверка доступности API сервера
if "api_server_checked" not in st.session_state:
    try:
        with httpx.Client(timeout=5.0) as client:
            health_response = client.get(f"{API_BASE_URL}/health")
            if health_response.status_code == 200:
                st.session_state.api_server_checked = True
                st.session_state.api_server_available = True
            else:
                st.session_state.api_server_checked = True
                st.session_state.api_server_available = False
    except Exception as e:
        st.session_state.api_server_checked = True
        st.session_state.api_server_available = False
        st.session_state.api_server_error = str(e)

# Предупреждение, если сервер недоступен
if st.session_state.get("api_server_checked") and not st.session_state.get("api_server_available", True):
    st.error("⚠️ **API сервер недоступен**")
    error_msg = st.session_state.get("api_server_error", "Connection refused")
    st.warning(f"**Детали:** {error_msg}")
    st.info("**💡 Решение:**")
    st.markdown(f"""
    **1. Запустите FastAPI сервер:**
    ```bash
    cd /mnt/ai/cnn/3dtoday
    PYTHONPATH=. uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
    ```
    
    **2. Проверьте, что сервер запущен:**
    - Откройте в браузере: `{API_BASE_URL}/docs`
    - Или проверьте: `curl {API_BASE_URL}/health`
    
    **3. Проверьте настройки подключения:**
    - Убедитесь, что `API_BASE_URL` в `config.env` указывает на правильный адрес
    - Текущий адрес: `{API_BASE_URL}`
    """)
    
    if st.button("🔄 Проверить снова"):
        del st.session_state.api_server_checked
        st.rerun()
    
    st.markdown("---")
    st.stop()

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

# Примеры успешных запросов
st.subheader("📋 Примеры успешных запросов")
example_queries = [
    "Ищу тренажеры для обучения студентов-медиков",
    "У меня появляются ниточки между деталями при печати PLA на Ender-3",
    "Печать отслаивается от стола при печати PETG",
    "Трещины в слоях при печати ABS на высоких температурах",
    "Недозаполнение при печати сложных моделей",
    "Проблемы с первым слоем на стеклянном столе",
    "Как настроить retraction для уменьшения stringing",
    "Печать деформируется при охлаждении"
]

# Отображение примеров в виде кнопок
cols = st.columns(4)
for idx, example in enumerate(example_queries):
    col_idx = idx % 4
    if cols[col_idx].button(f"📌 {example[:40]}..." if len(example) > 40 else f"📌 {example}", 
                            key=f"example_{idx}", 
                            use_container_width=True):
        st.session_state.selected_example = example
        st.rerun()

# Применение выбранного примера
if "selected_example" in st.session_state:
    st.info(f"💡 Выбран пример: **{st.session_state.selected_example}**")
    if st.button("✖️ Очистить пример"):
        del st.session_state.selected_example
        st.rerun()

st.markdown("---")

# Форма для нового запроса
with st.form("diagnostic_form", clear_on_submit=False):
    default_query = st.session_state.get("selected_example", "")
    query = st.text_area(
        "Опишите проблему",
        height=150,
        value=default_query,
        placeholder="Например: У меня появляются ниточки между деталями при печати PLA на Ender-3..."
    )
    
    # Очищаем выбранный пример после отправки формы
    if "selected_example" in st.session_state:
        del st.session_state.selected_example
    
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
    with st.spinner(f"🔍 Анализ проблемы и поиск решений... (это может занять до {int(DIAGNOSTIC_TIMEOUT)} секунд)"):
        try:
            with httpx.Client(timeout=DIAGNOSTIC_TIMEOUT) as client:
                response = client.post(
                    f"{API_BASE_URL}/api/diagnose",
                    json={
                        "query": query,
                        "printer_model": st.session_state.user_context.get("printer_model"),
                        "material": st.session_state.user_context.get("material"),
                        "problem_type": st.session_state.user_context.get("problem_type"),
                        "conversation_history": st.session_state.conversation_history[:-1]  # Без текущего запроса
                    },
                    timeout=DIAGNOSTIC_TIMEOUT
                )
                
                if response.status_code == 200:
                    diagnostic = response.json()
                elif response.status_code == 503:
                    # Сервис недоступен (LLM не запущен)
                    error_detail = response.json().get('detail', response.text) if response.headers.get('content-type', '').startswith('application/json') else response.text
                    st.error(f"⚠️ **LLM сервис недоступен**")
                    st.warning(error_detail)
                    st.info("**💡 Решение:**")
                    st.markdown("""
                    **Если используете Ollama:**
                    ```bash
                    ollama serve
                    ```
                    
                    **Если используете Gemini/OpenAI:**
                    - Проверьте, что `GEMINI_API_KEY` или `OPENAI_API_KEY` установлены в `config.env`
                    - Убедитесь, что провайдер доступен
                    
                    **Изменить провайдер:**
                    - Откройте `config.env`
                    - Установите `LLM_PROVIDER=gemini` (или `openai`)
                    - Перезапустите FastAPI сервер
                    """)
                    st.stop()
                else:
                    error_detail = response.json().get('detail', response.text) if response.headers.get('content-type', '').startswith('application/json') else response.text
                    st.error(f"❌ Ошибка API: {error_detail}")
                    st.stop()
        except httpx.TimeoutException as e:
            st.error(f"⏱️ Превышено время ожидания ответа ({int(DIAGNOSTIC_TIMEOUT)} секунд)")
            st.warning("💡 Поиск в базе знаний и генерация ответа могут занимать много времени.")
            st.info("**Рекомендации:**")
            st.markdown("""
            - Убедитесь, что FastAPI сервер запущен: `uvicorn backend.app.main:app --reload`
            - Проверьте, что LLM сервис (Ollama/OpenAI) работает корректно
            - Попробуйте упростить запрос или указать больше контекста (модель принтера, материал)
            - Увеличьте таймаут в `config.env`: `DIAGNOSTIC_TIMEOUT=600` (10 минут)
            """)
            st.stop()
        except httpx.ConnectError as e:
            st.error("❌ Не удалось подключиться к API серверу")
            st.warning(f"**Детали ошибки:** {str(e)}")
            st.info("**💡 Решение:**")
            st.markdown("""
            **1. Запустите FastAPI сервер:**
            ```bash
            cd /mnt/ai/cnn/3dtoday
            uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
            ```
            
            **2. Проверьте, что сервер запущен:**
            - Откройте в браузере: `http://localhost:8000/docs`
            - Или проверьте логи сервера
            
            **3. Проверьте настройки подключения:**
            - Убедитесь, что `API_BASE_URL` в `config.env` указывает на правильный адрес
            - По умолчанию: `http://localhost:8000`
            """)
            st.stop()
        except Exception as e:
            error_msg = str(e)
            # Проверяем различные варианты ошибок подключения
            connection_errors = [
                "connection refused",
                "errno 111",
                "errno 111]",
                "connect",
                "refused",
                "cannot connect",
                "не удалось подключиться"
            ]
            
            is_connection_error = any(err.lower() in error_msg.lower() for err in connection_errors)
            
            if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                st.error(f"⏱️ Превышено время ожидания ответа")
                st.warning("💡 Поиск в базе знаний и генерация ответа могут занимать много времени.")
                st.info("**Рекомендации:**")
                st.markdown("""
                - Убедитесь, что FastAPI сервер запущен: `uvicorn backend.app.main:app --reload`
                - Проверьте, что LLM сервис (Ollama/OpenAI) работает корректно
                - Попробуйте упростить запрос или указать больше контекста
                - Увеличьте таймаут в `config.env`: `DIAGNOSTIC_TIMEOUT=600`
                """)
            elif is_connection_error:
                st.error("❌ Ошибка подключения к API серверу")
                st.warning(f"**Детали ошибки:** {error_msg}")
                st.info("**💡 Решение:**")
                st.markdown("""
                **1. Запустите FastAPI сервер:**
                ```bash
                cd /mnt/ai/cnn/3dtoday
                uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
                ```
                
                **2. Проверьте, что сервер запущен:**
                - Откройте в браузере: `http://localhost:8000/docs`
                - Или проверьте логи сервера
                
                **3. Проверьте настройки подключения:**
                - Убедитесь, что `API_BASE_URL` в `config.env` указывает на правильный адрес
                - По умолчанию: `http://localhost:8000`
                """)
            else:
                st.error(f"❌ Ошибка API: {error_msg}")
                st.info("**💡 Убедитесь, что:**")
                st.markdown("""
                - FastAPI сервер запущен: `uvicorn backend.app.main:app --reload`
                - Сервер доступен по адресу из `API_BASE_URL` в `config.env`
                - Проверьте логи сервера для получения дополнительной информации
                """)
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
    
    ### Примеры успешных запросов:
    
    ✅ **"Ищу тренажеры для обучения студентов-медиков"**
    ✅ **"У меня появляются ниточки между деталями при печати PLA на Ender-3"**
    ✅ **"Печать отслаивается от стола при печати PETG"**
    ✅ **"Трещины в слоях при печати ABS на высоких температурах"**
    ✅ **"Недозаполнение при печати сложных моделей"**
    ✅ **"Проблемы с первым слоем на стеклянном столе"**
    ✅ **"Как настроить retraction для уменьшения stringing"**
    ✅ **"Печать деформируется при охлаждении"**
    
    💡 **Используйте кнопки с примерами выше** для быстрого выбора готового запроса
    
    ### Советы:
    
    💡 **Укажите контекст в боковой панели** - модель принтера и материал
    💡 **Приложите фото** - поможет точнее определить проблему (скоро будет доступно)
    💡 **Будьте конкретны** - чем подробнее описание, тем точнее диагностика
    """)



