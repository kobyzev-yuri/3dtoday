"""
Streamlit интерфейс для администраторов KB
Работает через FastAPI
"""

import streamlit as st
import httpx
import asyncio
import os
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / "config.env")

# Конфигурация API
API_BASE_URL = "http://localhost:8000"

# Настройка страницы
st.set_page_config(
    page_title="Управление KB - 3dtoday",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Управление базой знаний")

# Вкладки для навигации
tab1, tab2 = st.tabs(["➕ Добавление статей", "🧪 Инструкция по тестированию"])

with tab1:
    # Проверка статуса успешного добавления (после rerun)
    if "add_success_status" in st.session_state:
        success_info = st.session_state.add_success_status
        st.success(f"✅ {success_info.get('message', 'Статья успешно добавлена в KB!')}")
        if success_info.get('article_id'):
            st.info(f"**ID статьи:** `{success_info['article_id']}`")
        # Удаляем статус после отображения
        del st.session_state.add_success_status
        st.markdown("---")

    # Восстановление данных парсинга из pending (если были сохранены перед запросом)
    if "pending_add_parsed_document" in st.session_state and "pending_add_review" in st.session_state:
        # Восстанавливаем данные парсинга для повторной попытки
        if "parsed_document" not in st.session_state:
            st.session_state.parsed_document = st.session_state.pending_add_parsed_document
        if "review" not in st.session_state:
            st.session_state.review = st.session_state.pending_add_review
        if "admin_decision" not in st.session_state and "pending_add_admin_decision" in st.session_state:
            st.session_state.admin_decision = st.session_state.pending_add_admin_decision
        # Очищаем pending данные после восстановления
        del st.session_state.pending_add_parsed_document
        del st.session_state.pending_add_review
        if "pending_add_admin_decision" in st.session_state:
            del st.session_state.pending_add_admin_decision

# Боковая панель (вне вкладок, всегда видна)
with st.sidebar:
    st.header("⚙️ Настройки")
    
    # Инициализация session state для настроек
    if "relevance_threshold" not in st.session_state:
        st.session_state.relevance_threshold = 0.6
    if "admin_decision" not in st.session_state:
        st.session_state.admin_decision = None
    
    # Настройки KB
    st.subheader("📊 Настройки KB")
    
    relevance_threshold = st.slider(
        "Порог релевантности",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state.relevance_threshold,
        step=0.05,
        help="Минимальный порог релевантности для автоматического одобрения статьи (0.0-1.0)"
    )
    st.session_state.relevance_threshold = relevance_threshold
    
    st.markdown("---")
    
    # Выбор LLM провайдера и модели
    st.subheader("🤖 LLM Провайдер")
    
    # Загружаем значения из config.env
    default_provider = os.getenv("LLM_PROVIDER", "ollama")
    default_ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    default_openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")
    default_gemini_model = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
    
    # Проверяем, используется ли ProxyAPI
    openai_base_url = os.getenv("OPENAI_BASE_URL", "")
    gemini_base_url = os.getenv("GEMINI_BASE_URL", "")
    uses_proxyapi_openai = "proxyapi.ru" in openai_base_url.lower()
    uses_proxyapi_gemini = "proxyapi.ru" in gemini_base_url.lower()
    
    llm_provider = st.selectbox(
        "Провайдер:",
        ["openai", "ollama", "gemini"],
        index=["openai", "ollama", "gemini"].index(default_provider) if default_provider in ["openai", "ollama", "gemini"] else 1,
        format_func=lambda x: {
            "openai": f"GPT-4o ({'ProxyAPI.ru' if uses_proxyapi_openai else 'OpenAI'}) - {default_openai_model}",
            "ollama": f"Ollama - {default_ollama_model}",
            "gemini": f"Gemini ({'ProxyAPI.ru' if uses_proxyapi_gemini else 'Google'}) - {default_gemini_model}"
        }.get(x, x),
        help="Выберите провайдер LLM для анализа документов"
    )
    
    # Выбор модели в зависимости от провайдера
    if llm_provider == "openai":
        openai_models = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
        selected_model = st.selectbox(
            "Модель OpenAI:",
            openai_models,
            index=openai_models.index(default_openai_model) if default_openai_model in openai_models else 0
        )
    elif llm_provider == "ollama":
        # Получаем доступные модели Ollama
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    available_models = [m["name"] for m in data.get("models", [])]
                    if available_models:
                        # Предпочитаем qwen и llava модели
                        qwen_models = [m for m in available_models if 'qwen' in m.lower()]
                        llava_models = [m for m in available_models if 'llava' in m.lower()]
                        preferred = qwen_models + llava_models + [m for m in available_models if m not in qwen_models + llava_models]
                        
                        # Определяем индекс выбранной модели
                        current_model = default_ollama_model
                        if current_model not in preferred:
                            current_model = preferred[0] if preferred else available_models[0]
                        
                        selected_model = st.selectbox(
                            "Модель Ollama:",
                            preferred if preferred else available_models,
                            index=preferred.index(current_model) if current_model in preferred else 0,
                            help=f"Доступно моделей: {len(available_models)}"
                        )
                    else:
                        selected_model = st.text_input(
                            "Модель Ollama:",
                            value=default_ollama_model,
                            help="Модели не найдены. Введите название модели вручную"
                        )
                else:
                    selected_model = st.text_input(
                        "Модель Ollama:",
                        value=default_ollama_model,
                        help="Не удалось получить список моделей. Введите название модели вручную"
                    )
        except Exception as e:
            selected_model = st.text_input(
                "Модель Ollama:",
                value=default_ollama_model,
                help=f"Ошибка получения моделей: {e}. Введите название модели вручную"
            )
    else:  # gemini
        gemini_models = ["gemini-3-pro-preview", "gemini-pro", "gemini-1.5-pro"]
        selected_model = st.selectbox(
            "Модель Gemini:",
            gemini_models,
            index=gemini_models.index(default_gemini_model) if default_gemini_model in gemini_models else 0
        )
    
    st.markdown("---")
    
    # Настройки таймаутов
    st.subheader("⏱️ Таймауты (сек)")
    
    # Автоматическое определение таймаута для Ollama в зависимости от модели
    ollama_timeout_default = int(os.getenv("OLLAMA_TIMEOUT", "500"))
    if llm_provider == "ollama" and selected_model:
        heavy_models = ["qwen3:8b", "qwen3", "llama3.1:70b", "llama3:70b"]
        if any(heavy in selected_model.lower() for heavy in ["qwen3:8b", "qwen3", "70b"]):
            ollama_timeout_default = int(os.getenv("OLLAMA_TIMEOUT_HEAVY", "900"))
        else:
            ollama_timeout_default = int(os.getenv("OLLAMA_TIMEOUT_LIGHT", "100"))
    
    default_timeouts = {
        "API запросы": int(os.getenv("API_REQUEST_TIMEOUT", "300")),  # Увеличено для сложных операций
        "Парсинг документов": int(os.getenv("DOCUMENT_PARSER_TIMEOUT", "60")),
        "LLM генерация (Ollama)": ollama_timeout_default,
        "LLM генерация (OpenAI)": int(os.getenv("OPENAI_TIMEOUT", "120")),  # Увеличено для GPT-4o
        "MCP сервер": int(os.getenv("MCP_SERVER_TIMEOUT", "300")),  # Увеличено для полного цикла
        "RAG поиск": int(os.getenv("RAG_SEARCH_TIMEOUT", "30")),
        "Health check": int(os.getenv("HEALTH_CHECK_TIMEOUT", "10"))
    }
    
    timeout_values = {}
    for timeout_name, default_value in default_timeouts.items():
        timeout_values[timeout_name] = st.number_input(
            timeout_name,
            min_value=5,
            max_value=600,
            value=default_value,
            step=5,
            key=f"timeout_{timeout_name}"
        )
    
    # Сохранение в session state
    st.session_state.llm_provider = llm_provider
    st.session_state.selected_model = selected_model
    st.session_state.timeout_values = timeout_values
    
    st.markdown("---")
    
    st.header("📊 Статистика KB")
    
    if st.button("🔄 Обновить статистику"):
        try:
            health_timeout = timeout_values.get("Health check", int(os.getenv("HEALTH_CHECK_TIMEOUT", "10")))
            with httpx.Client(timeout=health_timeout) as client:
                response = client.get(f"{API_BASE_URL}/api/kb/statistics")
                if response.status_code == 200:
                    stats = response.json()
                    st.success("✅ Статистика обновлена")
                    st.metric("Статей", stats.get("text_articles", 0))
                    st.metric("Изображений", stats.get("images", 0))
                    st.metric("Всего векторов", stats.get("total_vectors", 0))
        except Exception as e:
            st.error(f"❌ Ошибка: {e}")
    
        st.markdown("---")
        st.info("💡 Используйте форму ниже для добавления статей в KB")

    # Основной интерфейс
    st.subheader("📝 Добавление статьи в KB")

# Выбор способа ввода
# Сохраняем выбранный метод ввода в session_state
if "input_method" not in st.session_state:
    st.session_state.input_method = "🤖 По URL (через LLM - GPT-4o/Gemini)"

# Определяем индекс выбранного метода
default_index = 0
if "input_method" in st.session_state:
    methods = ["🔗 По URL/Файлу (автоматический парсинг)", "🤖 По URL (через LLM - GPT-4o/Gemini)", "📝 Ручной ввод", "📄 Импорт из JSON"]
    if st.session_state.input_method in methods:
        default_index = methods.index(st.session_state.input_method)

input_method = st.radio(
    "Способ добавления документа:",
    ["🔗 По URL/Файлу (автоматический парсинг)", "🤖 По URL (через LLM - GPT-4o/Gemini)", "📝 Ручной ввод", "📄 Импорт из JSON"],
    index=default_index,
    horizontal=True
)

# Сохраняем выбранный метод в session_state
st.session_state.input_method = input_method

st.markdown("---")

if input_method == "🤖 По URL (через LLM - GPT-4o/Gemini)":
    # Парсинг через LLM напрямую
    st.info("💡 **Новый метод**: LLM сам загружает контент и формирует JSON для KB")
    
    # Используем провайдер из sidebar (без дублирования выбора)
    sidebar_provider = st.session_state.get("llm_provider", "ollama")
    sidebar_model = st.session_state.get("selected_model", "qwen2.5:1.5b")
    
    # Предупреждение, если выбран Ollama (может не поддерживать tool calls)
    if sidebar_provider == "ollama":
        st.warning("⚠️ **Внимание**: В sidebar выбран Ollama. Для LLM парсинга (требуются tool calls) рекомендуется использовать OpenAI или Gemini. Измените провайдер в sidebar (слева) или используйте метод '🔗 По URL/Файлу (автоматический парсинг)' для Ollama.")
        # Для Ollama используем OpenAI как fallback
        llm_provider_choice = "openai"
        model_choice = "gpt-4o"
        st.info(f"📋 Будет использован: **{llm_provider_choice.upper()}** ({model_choice}) - измените провайдер в sidebar для другого выбора")
    else:
        # Используем провайдер из sidebar напрямую
        llm_provider_choice = sidebar_provider
        model_choice = sidebar_model
        st.info(f"📋 Используется провайдер из настроек (sidebar): **{llm_provider_choice.upper()}** ({model_choice})")
    
    with st.form("llm_url_form"):
        source = st.text_input(
            "URL документа",
            placeholder="https://3dtoday.ru/...",
            help=f"Будет использован провайдер из sidebar: {sidebar_provider.upper()} ({sidebar_model})"
        )
        
        submitted_llm = st.form_submit_button("🤖 Анализировать через LLM", type="primary", use_container_width=True)
    
    # Проверяем наличие уже распарсенного документа в session_state
    if "llm_parsed_document" in st.session_state and st.session_state.llm_parsed_document:
        parsed_document = st.session_state.llm_parsed_document
        source = st.session_state.get("llm_source", "")
        llm_provider_choice = st.session_state.get("llm_provider_choice", "openai")
        model_choice = st.session_state.get("llm_model_choice", "gpt-4o")
        
        st.success(f"✅ URL успешно проанализирован через {llm_provider_choice.upper()} ({model_choice})!")
        
        # Отображение результата
        st.subheader("📄 Результат анализа LLM")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Заголовок:**", parsed_document.get("title", ""))
            st.write("**Раздел:**", parsed_document.get("section", "unknown"))
            st.write("**Тип контента:**", parsed_document.get("content_type", "article"))
            st.write("**Релевантность:**", f"{parsed_document.get('relevance_score', 0):.2f}")
            st.write("**Качество:**", f"{parsed_document.get('quality_score', 0):.2f}")
        
        with col2:
            st.write("**URL:**", parsed_document.get("url", source))
            st.write("**Дата:**", parsed_document.get("date", ""))
            if parsed_document.get("author"):
                st.write("**Автор:**", parsed_document["author"])
            if parsed_document.get("tags"):
                st.write("**Теги:**", ", ".join(parsed_document["tags"]))
        
        # Abstract
        if parsed_document.get("abstract"):
            st.subheader("📝 Abstract")
            st.info(parsed_document["abstract"])
        
        # Содержимое
        if parsed_document.get("content"):
            with st.expander("📄 Содержимое"):
                st.markdown(parsed_document["content"][:2000] + "..." if len(parsed_document["content"]) > 2000 else parsed_document["content"])
        
        # Детали
        if parsed_document.get("problem"):
            st.subheader("🔍 Детали")
            st.write("**Проблема:**", parsed_document["problem"])
            
            if parsed_document.get("symptoms"):
                st.write("**Симптомы:**")
                for symptom in parsed_document["symptoms"]:
                    st.write(f"- {symptom}")
            
            if parsed_document.get("solutions"):
                st.write("**Решения:**")
                for i, solution in enumerate(parsed_document["solutions"], 1):
                    if isinstance(solution, dict):
                        st.write(f"{i}. {solution.get('description', '')}")
                    else:
                        st.write(f"{i}. {solution}")
        
        # Решение администратора
        st.markdown("---")
        st.subheader("👤 Решение администратора")
        
        if "admin_decision" not in st.session_state or st.session_state.admin_decision is None:
            is_relevant = parsed_document.get("is_relevant", False)
            st.session_state.admin_decision = "approve" if is_relevant else "needs_review"
        
        admin_decision = st.radio(
            "Ваше решение:",
            ["approve", "reject", "needs_review"],
            index=["approve", "reject", "needs_review"].index(st.session_state.admin_decision) if st.session_state.admin_decision in ["approve", "reject", "needs_review"] else 0,
            format_func=lambda x: {
                "approve": "✅ Одобрить и добавить в KB",
                "reject": "❌ Отклонить",
                "needs_review": "⚠️ Требуется дополнительная проверка"
            }.get(x, x)
        )
        
        st.session_state.admin_decision = admin_decision
        
        # Кнопка добавления
        if admin_decision == "approve":
            if st.button("✅ Добавить в KB", type="primary", use_container_width=True):
                # Сохраняем данные парсинга перед запросом (на случай ошибки)
                st.session_state.pending_add_parsed_document = parsed_document
                st.session_state.pending_add_review = {
                    "decision": "approve",
                    "relevance_score": parsed_document.get("relevance_score", 0.0),
                    "quality_score": parsed_document.get("quality_score", 0.0),
                    "summary": parsed_document
                }
                st.session_state.pending_add_admin_decision = admin_decision
                
                try:
                    # Увеличиваем таймаут для индексации (может занимать много времени)
                    api_timeout = st.session_state.get("timeout_values", {}).get("API запросы", int(os.getenv("API_REQUEST_TIMEOUT", "300")))
                    index_timeout = max(float(api_timeout), 600.0)  # Минимум 10 минут для индексации
                    
                    with st.spinner(f"💾 Индексация статьи... (это может занять до {int(index_timeout/60)} минут)"):
                        with httpx.Client(timeout=index_timeout) as add_client:
                            add_response = add_client.post(
                                f"{API_BASE_URL}/api/kb/articles/add_from_parse",
                                json={
                                    "parsed_document": parsed_document,
                                    "review": {
                                        "decision": "approve",
                                        "relevance_score": parsed_document.get("relevance_score", 0.0),
                                        "quality_score": parsed_document.get("quality_score", 0.0),
                                        "summary": parsed_document
                                    },
                                    "admin_decision": admin_decision,
                                    "relevance_threshold": st.session_state.relevance_threshold
                                },
                                timeout=index_timeout
                            )
                            
                            if add_response.status_code == 200:
                                result = add_response.json()
                                # Сохраняем статус успеха перед rerun
                                st.session_state.add_success_status = {
                                    "message": "Статья успешно добавлена в KB!",
                                    "article_id": result.get('article_id', 'unknown')
                                }
                                # Очищаем pending данные
                                if "pending_add_parsed_document" in st.session_state:
                                    del st.session_state.pending_add_parsed_document
                                if "pending_add_review" in st.session_state:
                                    del st.session_state.pending_add_review
                                if "pending_add_admin_decision" in st.session_state:
                                    del st.session_state.pending_add_admin_decision
                                # Очищаем данные парсинга после успешного добавления
                                if "llm_parsed_document" in st.session_state:
                                    del st.session_state.llm_parsed_document
                                if "llm_source" in st.session_state:
                                    del st.session_state.llm_source
                                if "llm_provider_choice" in st.session_state:
                                    del st.session_state.llm_provider_choice
                                if "llm_model_choice" in st.session_state:
                                    del st.session_state.llm_model_choice
                                if "admin_decision" in st.session_state:
                                    del st.session_state.admin_decision
                                st.rerun()
                            else:
                                error_detail = add_response.json().get('detail', add_response.text) if add_response.headers.get('content-type', '').startswith('application/json') else add_response.text
                                st.error(f"❌ Ошибка добавления: {error_detail}")
                                # Очищаем pending данные при ошибке
                                if "pending_add_parsed_document" in st.session_state:
                                    del st.session_state.pending_add_parsed_document
                                if "pending_add_review" in st.session_state:
                                    del st.session_state.pending_add_review
                                if "pending_add_admin_decision" in st.session_state:
                                    del st.session_state.pending_add_admin_decision
                except httpx.TimeoutException as e:
                    st.error(f"⏱️ Превышено время ожидания ответа ({int(index_timeout)} секунд)")
                    st.warning("💡 Индексация статьи может занимать много времени из-за генерации эмбеддингов.")
                    st.info("**Рекомендации:**")
                    st.markdown("""
                    - Убедитесь, что FastAPI сервер запущен
                    - Проверьте, что модель эмбеддингов загружена
                    - Попробуйте еще раз или увеличьте таймаут в настройках
                    """)
                    # Очищаем pending данные при таймауте
                    if "pending_add_parsed_document" in st.session_state:
                        del st.session_state.pending_add_parsed_document
                    if "pending_add_review" in st.session_state:
                        del st.session_state.pending_add_review
                    if "pending_add_admin_decision" in st.session_state:
                        del st.session_state.pending_add_admin_decision
                except Exception as e:
                    st.error(f"❌ Ошибка подключения к API: {e}")
                    # Очищаем pending данные при ошибке
                    if "pending_add_parsed_document" in st.session_state:
                        del st.session_state.pending_add_parsed_document
                    if "pending_add_review" in st.session_state:
                        del st.session_state.pending_add_review
                    if "pending_add_admin_decision" in st.session_state:
                        del st.session_state.pending_add_admin_decision
    
    elif submitted_llm and source:
        api_timeout = st.session_state.get("timeout_values", {}).get("API запросы", int(os.getenv("API_REQUEST_TIMEOUT", "300")))
        
        # Получаем таймаут для выбранного LLM провайдера
        llm_timeout = None
        if llm_provider_choice == "openai":
            llm_timeout = st.session_state.get("timeout_values", {}).get("LLM генерация (OpenAI)", int(os.getenv("OPENAI_TIMEOUT", "120")))
        elif llm_provider_choice == "gemini":
            # Для Gemini используем таймаут OpenAI (если нет отдельного)
            llm_timeout = st.session_state.get("timeout_values", {}).get("LLM генерация (OpenAI)", int(os.getenv("GEMINI_TIMEOUT", "120")))
        
        # Общий таймаут должен быть больше таймаута LLM + буфер
        if llm_timeout:
            actual_timeout = max(api_timeout, llm_timeout + 60)  # Буфер 60 секунд
        else:
            actual_timeout = max(api_timeout, 300)
        
        with st.spinner(f"🤖 LLM анализирует URL... (это может занять время, таймаут: {actual_timeout} сек)"):
            try:
                request_data = {
                    "url": source,
                    "llm_provider": llm_provider_choice,
                    "model": model_choice
                }
                
                # Добавляем таймаут LLM, если указан
                if llm_timeout:
                    request_data["llm_timeout"] = llm_timeout
                
                with httpx.Client(timeout=float(actual_timeout)) as client:
                    response = client.post(
                        f"{API_BASE_URL}/api/kb/articles/parse_with_llm",
                        json=request_data,
                        timeout=float(actual_timeout)
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        parsed_document = result.get("parsed_document", {})
                        
                        # Сохраняем в session_state для сохранения после rerun
                        st.session_state.llm_parsed_document = parsed_document
                        st.session_state.llm_source = source
                        st.session_state.llm_provider_choice = llm_provider_choice
                        st.session_state.llm_model_choice = model_choice
                        
                        st.success(f"✅ URL успешно проанализирован через {llm_provider_choice.upper()} ({result.get('model', 'unknown')})!")
                        
                        # Отображение результата
                        st.subheader("📄 Результат анализа LLM")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**Заголовок:**", parsed_document.get("title", ""))
                            st.write("**Раздел:**", parsed_document.get("section", "unknown"))
                            st.write("**Тип контента:**", parsed_document.get("content_type", "article"))
                            st.write("**Релевантность:**", f"{parsed_document.get('relevance_score', 0):.2f}")
                            st.write("**Качество:**", f"{parsed_document.get('quality_score', 0):.2f}")
                        
                        with col2:
                            st.write("**URL:**", parsed_document.get("url", source))
                            st.write("**Дата:**", parsed_document.get("date", ""))
                            if parsed_document.get("author"):
                                st.write("**Автор:**", parsed_document["author"])
                            if parsed_document.get("tags"):
                                st.write("**Теги:**", ", ".join(parsed_document["tags"]))
                        
                        # Abstract
                        if parsed_document.get("abstract"):
                            st.subheader("📝 Abstract")
                            st.info(parsed_document["abstract"])
                        
                        # Содержимое
                        if parsed_document.get("content"):
                            with st.expander("📄 Содержимое"):
                                st.markdown(parsed_document["content"][:2000] + "..." if len(parsed_document["content"]) > 2000 else parsed_document["content"])
                        
                        # Детали
                        if parsed_document.get("problem"):
                            st.subheader("🔍 Детали")
                            st.write("**Проблема:**", parsed_document["problem"])
                            
                            if parsed_document.get("symptoms"):
                                st.write("**Симптомы:**")
                                for symptom in parsed_document["symptoms"]:
                                    st.write(f"- {symptom}")
                            
                            if parsed_document.get("solutions"):
                                st.write("**Решения:**")
                                for i, solution in enumerate(parsed_document["solutions"], 1):
                                    if isinstance(solution, dict):
                                        st.write(f"{i}. {solution.get('description', '')}")
                                    else:
                                        st.write(f"{i}. {solution}")
                        
                        # Решение администратора
                        st.markdown("---")
                        st.subheader("👤 Решение администратора")
                        
                        if "admin_decision" not in st.session_state or st.session_state.admin_decision is None:
                            is_relevant = parsed_document.get("is_relevant", False)
                            st.session_state.admin_decision = "approve" if is_relevant else "needs_review"
                        
                        admin_decision = st.radio(
                            "Ваше решение:",
                            ["approve", "reject", "needs_review"],
                            index=["approve", "reject", "needs_review"].index(st.session_state.admin_decision) if st.session_state.admin_decision in ["approve", "reject", "needs_review"] else 0,
                            format_func=lambda x: {
                                "approve": "✅ Одобрить и добавить в KB",
                                "reject": "❌ Отклонить",
                                "needs_review": "⚠️ Требуется дополнительная проверка"
                            }.get(x, x)
                        )
                        
                        st.session_state.admin_decision = admin_decision
                        
                        # Кнопка добавления
                        if admin_decision == "approve":
                            if st.button("✅ Добавить в KB", type="primary", use_container_width=True):
                                try:
                                    with httpx.Client(timeout=float(api_timeout)) as add_client:
                                        add_response = add_client.post(
                                            f"{API_BASE_URL}/api/kb/articles/add_from_parse",
                                            json={
                                                "parsed_document": parsed_document,
                                                "review": {
                                                    "decision": "approve",
                                                    "relevance_score": parsed_document.get("relevance_score", 0.0),
                                                    "quality_score": parsed_document.get("quality_score", 0.0),
                                                    "summary": parsed_document
                                                },
                                                "admin_decision": admin_decision,
                                                "relevance_threshold": st.session_state.relevance_threshold
                                            },
                                            timeout=float(api_timeout)
                                        )
                                        
                                        if add_response.status_code == 200:
                                            result = add_response.json()
                                            # Сохраняем статус успеха перед rerun
                                            st.session_state.add_success_status = {
                                                "message": "Статья успешно добавлена в KB!",
                                                "article_id": result.get('article_id', 'unknown')
                                            }
                                            # Очищаем данные парсинга после успешного добавления
                                            if "llm_parsed_document" in st.session_state:
                                                del st.session_state.llm_parsed_document
                                            if "llm_source" in st.session_state:
                                                del st.session_state.llm_source
                                            if "llm_provider_choice" in st.session_state:
                                                del st.session_state.llm_provider_choice
                                            if "llm_model_choice" in st.session_state:
                                                del st.session_state.llm_model_choice
                                            if "admin_decision" in st.session_state:
                                                del st.session_state.admin_decision
                                            st.rerun()
                                        else:
                                            error_detail = add_response.json().get('detail', add_response.text)
                                            st.error(f"❌ Ошибка добавления: {error_detail}")
                                except Exception as e:
                                    st.error(f"❌ Ошибка подключения к API: {e}")
                    else:
                        error_detail = response.json().get('detail', response.text) if response.headers.get('content-type', '').startswith('application/json') else response.text
                        st.error(f"❌ Ошибка анализа через LLM: {error_detail}")
                        
            except Exception as e:
                st.error(f"❌ Ошибка подключения к API: {e}")
                st.info("💡 Убедитесь, что FastAPI сервер запущен")

elif input_method == "🔗 По URL/Файлу (автоматический парсинг)":
    # Парсинг по URL или файлу
    st.info("💡 Поддерживаются: HTML/URL, PDF документы, TXT файлы, JSON файлы")
    
    # Выбор способа ввода: URL или файл
    input_type = st.radio(
        "Способ ввода:",
        ["📎 Загрузить файл", "🔗 Ввести URL/путь"],
        horizontal=True
    )
    
    with st.form("url_form", clear_on_submit=False):
        if input_type == "📎 Загрузить файл":
            uploaded_file = st.file_uploader(
                "Загрузите файл",
                type=["pdf", "txt", "json", "html"],
                help="Перетащите файл сюда или нажмите для выбора. Поддерживаются: PDF, TXT, JSON, HTML"
            )
            
            if uploaded_file:
                # Сохраняем файл во временную директорию
                import tempfile
                import os
                temp_dir = Path(tempfile.gettempdir()) / "kb_uploads"
                temp_dir.mkdir(exist_ok=True)
                
                # Определяем расширение файла
                file_ext = Path(uploaded_file.name).suffix.lower()
                temp_file_path = temp_dir / f"{uploaded_file.name}"
                
                # Сохраняем файл
                with open(temp_file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                source = str(temp_file_path)
                st.session_state.uploaded_file_path = source
                st.session_state.uploaded_file_name = uploaded_file.name
                st.success(f"✅ Файл загружен: {uploaded_file.name} ({uploaded_file.size} байт)")
                
                # Автоматически определяем тип источника
                if file_ext == ".pdf":
                    source_type = "pdf"
                elif file_ext == ".txt":
                    source_type = "html"  # TXT обрабатывается как текст
                elif file_ext == ".json":
                    source_type = "json"
                elif file_ext == ".html":
                    source_type = "html"
                else:
                    source_type = "auto"
                st.session_state.uploaded_source_type = source_type
            else:
                source = None
                source_type = "auto"
                if "uploaded_file_path" in st.session_state:
                    # Используем ранее загруженный файл
                    source = st.session_state.uploaded_file_path
                    source_type = st.session_state.get("uploaded_source_type", "auto")
        else:
            # Ввод URL или пути к файлу
            col1, col2 = st.columns(2)
            
            with col1:
                source = st.text_input(
                    "URL или путь к файлу *",
                    placeholder="https://3dtoday.ru/... или /path/to/file.pdf"
                )
            
            with col2:
                source_type = st.selectbox(
                    "Тип источника (автоопределение если не указан)",
                    ["auto", "html", "pdf", "json", "url"],
                    help="auto - автоматическое определение типа"
                )
            
            uploaded_file = None
        
        submitted_url = st.form_submit_button("📥 Скачать и проанализировать документ", use_container_width=True)
    
    # Проверяем наличие уже распарсенного документа в session_state (после rerun)
    if "parsed_document" in st.session_state and st.session_state.parsed_document:
        parsed_document = st.session_state.parsed_document
        review = st.session_state.get("review", {})
        summary = review.get("summary", {})
        source = st.session_state.get("document_source", "")
        
        st.success("✅ Документ успешно скачан и проанализирован!")
        
        # Решение библиотекаря
        decision = review.get("decision", "needs_review")
        reason = review.get("reason", "")
        relevance_score = review.get("relevance_score", 0.0)
        quality_score = review.get("quality_score", 0.0)
        
        st.subheader("📋 Решение библиотекаря")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if decision == "approve":
                st.success(f"✅ **Одобрено**")
            elif decision == "reject":
                st.error(f"❌ **Отклонено**")
            else:
                st.warning(f"⚠️ **Требуется проверка**")
        
        with col2:
            threshold = st.session_state.relevance_threshold
            threshold_color = "normal" if relevance_score >= threshold else "inverse"
            st.metric(
                "Релевантность",
                f"{relevance_score:.2f}",
                delta=f"Порог: {threshold:.2f}",
                delta_color=threshold_color
            )
        
        with col3:
            st.metric("Качество", f"{quality_score:.2f}")
        
        st.info(f"**Причина:** {reason}")
        
        # Решение администратора
        st.markdown("---")
        st.subheader("👤 Решение администратора")
        
        # Инициализация admin_decision из session_state или из решения библиотекаря
        if "admin_decision" not in st.session_state or st.session_state.admin_decision is None:
            st.session_state.admin_decision = decision
        
        admin_decision = st.radio(
            "Ваше решение:",
            ["approve", "reject", "needs_review"],
            index=["approve", "reject", "needs_review"].index(st.session_state.admin_decision) if st.session_state.admin_decision in ["approve", "reject", "needs_review"] else 2,
            format_func=lambda x: {
                "approve": "✅ Одобрить и добавить в KB",
                "reject": "❌ Отклонить",
                "needs_review": "⚠️ Требуется дополнительная проверка"
            }.get(x, x),
            help="Вы можете переопределить решение библиотекаря"
        )
        
        st.session_state.admin_decision = admin_decision
        
        # Предупреждение если решение переопределено
        if admin_decision != decision:
            if admin_decision == "approve" and decision == "reject":
                st.warning("⚠️ Вы одобряете статью, отклоненную библиотекарем")
            elif admin_decision == "reject" and decision == "approve":
                st.warning("⚠️ Вы отклоняете статью, одобренную библиотекарем")
        
        # Предупреждение если релевантность ниже порога
        if relevance_score < st.session_state.relevance_threshold and admin_decision == "approve":
            st.warning(
                f"⚠️ Релевантность ({relevance_score:.2f}) ниже установленного порога "
                f"({st.session_state.relevance_threshold:.2f})"
            )
        
        # Проверка на дублирование
        duplicate_check = review.get("duplicate_check", {})
        if duplicate_check.get("is_duplicate"):
            st.warning("⚠️ **Обнаружены похожие документы в KB:**")
            for i, similar_title in enumerate(duplicate_check.get("similar_docs", [])[:3], 1):
                st.write(f"{i}. {similar_title}")
        
        # Abstract
        abstract = review.get("abstract", "")
        if abstract:
            st.subheader("📝 Abstract (краткое изложение)")
            st.info(abstract)
        
        st.markdown("---")
        
        # Отображение результатов
        st.subheader("📄 Распарсенный документ")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Заголовок:**", parsed_document.get("title", ""))
            st.write("**Тип контента:**", parsed_document.get("content_type", "article"))
            st.write("**Раздел:**", parsed_document.get("section", "unknown"))
            st.write("**Дата:**", parsed_document.get("date", ""))
            if parsed_document.get("author"):
                st.write("**Автор:**", parsed_document["author"])
        
        with col2:
            st.write("**Источник:**", source[:100] if len(source) > 100 else source)
            if parsed_document.get("url"):
                st.write("**URL:**", parsed_document["url"])
            if parsed_document.get("tags"):
                st.write("**Теги:**", ", ".join(parsed_document["tags"]))
            st.write("**Изображений:**", len(parsed_document.get("images", [])))
        
        # Краткое изложение от агента-библиотекаря
        st.subheader("📋 Краткое изложение (от агента-библиотекаря)")
        
        content_type = summary.get("content_type", "article") if summary else "article"
        st.info(f"**Тип контента:** {content_type}")
        
        if summary:
            st.markdown(summary.get("summary", ""))
        
        # Детали изложения в зависимости от типа контента
        with st.expander("🔍 Детали анализа"):
            if content_type == "article":
                st.write("**Проблема:**", summary.get("problem", ""))
                
                if summary.get("symptoms"):
                    st.write("**Симптомы:**")
                    for symptom in summary["symptoms"]:
                        st.write(f"- {symptom}")
                
                if summary.get("solutions"):
                    st.write("**Решения:**")
                    for i, solution in enumerate(summary["solutions"], 1):
                        st.write(f"{i}. {solution.get('description', '')}")
                        if solution.get("parameters"):
                            st.write(f"   Параметры: {solution['parameters']}")
                
                if summary.get("printer_models"):
                    st.write("**Принтеры:**", ", ".join(summary["printer_models"]))
                
                if summary.get("materials"):
                    st.write("**Материалы:**", ", ".join(summary["materials"]))
            
            elif content_type == "documentation":
                st.write("**Тип документации:**", summary.get("documentation_type", ""))
                if summary.get("equipment_models"):
                    st.write("**Модели оборудования:**", ", ".join(summary["equipment_models"]))
                if summary.get("key_specifications"):
                    st.write("**Характеристики:**")
                    for k, v in summary["key_specifications"].items():
                        st.write(f"- {k}: {v}")
            
            elif content_type == "comparison":
                st.write("**Тип сравнения:**", summary.get("comparison_type", ""))
                if summary.get("compared_items"):
                    st.write("**Сравниваемые варианты:**", ", ".join(summary["compared_items"]))
                if summary.get("key_differences"):
                    st.write("**Ключевые отличия:**")
                    for item, diffs in summary["key_differences"].items():
                        st.write(f"- **{item}**: {', '.join(diffs)}")
            
            elif content_type == "technical":
                st.write("**Тема:**", summary.get("topic", ""))
                if summary.get("key_characteristics"):
                    st.write("**Характеристики:**")
                    for k, v in summary["key_characteristics"].items():
                        st.write(f"- {k}: {v}")
            
            if summary.get("key_points"):
                st.write("**Ключевые моменты:**")
                for kp in summary["key_points"]:
                    st.write(f"- {kp}")
        
        # Изображения из документа
        if parsed_document.get("images"):
            st.subheader("🖼️ Изображения из документа")
            for i, img in enumerate(parsed_document["images"][:5], 1):  # Показываем первые 5
                with st.expander(f"Изображение {i}: {img.get('alt', 'Без описания')}"):
                    try:
                        st.image(img["url"], use_container_width=True)
                    except:
                        st.info(f"Не удалось загрузить изображение: {img['url']}")
                    if img.get("description"):
                        st.caption(img["description"])
        
        # Рекомендации библиотекаря
        recommendations = review.get("recommendations", [])
        if recommendations:
            st.subheader("💡 Рекомендации библиотекаря")
            for rec in recommendations:
                st.write(f"- {rec}")
        
        # Кнопки действий в зависимости от решения администратора
        st.markdown("---")
        st.subheader("🎯 Действия")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if admin_decision == "approve":
                                if st.button("✅ Добавить в KB", type="primary", use_container_width=True):
                                    # Сохраняем данные перед запросом
                                    st.session_state.pending_add_parsed_document = parsed_document
                                    st.session_state.pending_add_review = review
                                    st.session_state.pending_add_admin_decision = admin_decision
                                    
                                    # Добавление статьи в KB
                                    try:
                                        # Увеличиваем таймаут для индексации
                                        api_timeout = st.session_state.get("timeout_values", {}).get("API запросы", int(os.getenv("API_REQUEST_TIMEOUT", "300")))
                                        index_timeout = max(float(api_timeout), 600.0)  # Минимум 10 минут
                                        
                                        with st.spinner(f"💾 Индексация статьи... (это может занять до {int(index_timeout/60)} минут)"):
                                            with httpx.Client(timeout=index_timeout) as client:
                                                add_response = client.post(
                                                    f"{API_BASE_URL}/api/kb/articles/add_from_parse",
                                                    json={
                                                        "parsed_document": parsed_document,
                                                        "review": review,
                                                        "admin_decision": admin_decision,
                                                        "relevance_threshold": st.session_state.relevance_threshold
                                                    },
                                                    timeout=index_timeout
                                                )
                                                
                                                if add_response.status_code == 200:
                                                    result = add_response.json()
                                                    # Сохраняем статус успеха перед rerun
                                                    st.session_state.add_success_status = {
                                                        "message": "Статья успешно добавлена в KB!",
                                                        "article_id": result.get('article_id', 'unknown')
                                                    }
                                                    # Очищаем pending данные
                                                    if "pending_add_parsed_document" in st.session_state:
                                                        del st.session_state.pending_add_parsed_document
                                                    if "pending_add_review" in st.session_state:
                                                        del st.session_state.pending_add_review
                                                    if "pending_add_admin_decision" in st.session_state:
                                                        del st.session_state.pending_add_admin_decision
                                                    # Очистка session state
                                                    if "parsed_document" in st.session_state:
                                                        del st.session_state.parsed_document
                                                    if "review" in st.session_state:
                                                        del st.session_state.review
                                                    if "summary" in st.session_state:
                                                        del st.session_state.summary
                                                    if "document_source" in st.session_state:
                                                        del st.session_state.document_source
                                                    if "admin_decision" in st.session_state:
                                                        del st.session_state.admin_decision
                                                    st.rerun()
                                                else:
                                                    error_detail = add_response.json().get('detail', add_response.text) if add_response.headers.get('content-type', '').startswith('application/json') else add_response.text
                                                    st.error(f"❌ Ошибка добавления: {error_detail}")
                                                    # Очищаем pending данные при ошибке
                                                    if "pending_add_parsed_document" in st.session_state:
                                                        del st.session_state.pending_add_parsed_document
                                                    if "pending_add_review" in st.session_state:
                                                        del st.session_state.pending_add_review
                                                    if "pending_add_admin_decision" in st.session_state:
                                                        del st.session_state.pending_add_admin_decision
                                    except httpx.TimeoutException as e:
                                        st.error(f"⏱️ Превышено время ожидания ответа ({int(index_timeout)} секунд)")
                                        st.warning("💡 Индексация статьи может занимать много времени из-за генерации эмбеддингов.")
                                        st.info("**Рекомендации:**")
                                        st.markdown("""
                                        - Убедитесь, что FastAPI сервер запущен
                                        - Проверьте, что модель эмбеддингов загружена
                                        - Попробуйте еще раз или увеличьте таймаут в настройках
                                        """)
                                        # Очищаем pending данные при таймауте
                                        if "pending_add_parsed_document" in st.session_state:
                                            del st.session_state.pending_add_parsed_document
                                        if "pending_add_review" in st.session_state:
                                            del st.session_state.pending_add_review
                                        if "pending_add_admin_decision" in st.session_state:
                                            del st.session_state.pending_add_admin_decision
                                    except Exception as e:
                                        st.error(f"❌ Ошибка подключения к API: {e}")
                                        # Очищаем pending данные при ошибке
                                        if "pending_add_parsed_document" in st.session_state:
                                            del st.session_state.pending_add_parsed_document
                                        if "pending_add_review" in st.session_state:
                                            del st.session_state.pending_add_review
                                        if "pending_add_admin_decision" in st.session_state:
                                            del st.session_state.pending_add_admin_decision
            elif admin_decision == "reject":
                st.info("📋 Документ отклонен. Он не будет добавлен в KB.")
                if st.button("🔄 Очистить форму", use_container_width=True):
                    if "parsed_document" in st.session_state:
                        del st.session_state.parsed_document
                    if "review" in st.session_state:
                        del st.session_state.review
                    if "summary" in st.session_state:
                        del st.session_state.summary
                    if "document_source" in st.session_state:
                        del st.session_state.document_source
                    if "admin_decision" in st.session_state:
                        del st.session_state.admin_decision
                    st.rerun()
            else:  # needs_review
                st.warning("⚠️ Требуется дополнительная проверка перед добавлением в KB")
                if st.button("💾 Сохранить для проверки", use_container_width=True):
                    st.info("💡 Документ сохранен в сессии. Вы можете вернуться к нему позже.")
        
        with col2:
            if st.button("🔄 Сбросить решение", use_container_width=True):
                if "parsed_document" in st.session_state:
                    del st.session_state.parsed_document
                if "review" in st.session_state:
                    del st.session_state.review
                if "summary" in st.session_state:
                    del st.session_state.summary
                if "document_source" in st.session_state:
                    del st.session_state.document_source
                if "admin_decision" in st.session_state:
                    del st.session_state.admin_decision
                st.rerun()
    
    elif submitted_url and (source or st.session_state.get("uploaded_file_path")):
        # Используем загруженный файл, если есть
        if not source and st.session_state.get("uploaded_file_path"):
            source = st.session_state.uploaded_file_path
            source_type = st.session_state.get("uploaded_source_type", "auto")
        api_timeout = st.session_state.get("timeout_values", {}).get("API запросы", int(os.getenv("API_REQUEST_TIMEOUT", "300")))
        mcp_timeout = st.session_state.get("timeout_values", {}).get("MCP сервер", int(os.getenv("MCP_SERVER_TIMEOUT", "300")))
        
        # Получаем таймаут для выбранного LLM провайдера
        llm_provider_for_timeout = st.session_state.get("llm_provider", os.getenv("LLM_PROVIDER", "ollama"))
        llm_timeout = None
        if llm_provider_for_timeout == "ollama":
            llm_timeout = st.session_state.get("timeout_values", {}).get("LLM генерация (Ollama)", int(os.getenv("OLLAMA_TIMEOUT", "500")))
        elif llm_provider_for_timeout == "openai":
            llm_timeout = st.session_state.get("timeout_values", {}).get("LLM генерация (OpenAI)", int(os.getenv("OPENAI_TIMEOUT", "120")))
        elif llm_provider_for_timeout == "gemini":
            # Для Gemini используем таймаут OpenAI (если нет отдельного)
            llm_timeout = st.session_state.get("timeout_values", {}).get("LLM генерация (OpenAI)", int(os.getenv("GEMINI_TIMEOUT", "120")))
        
        # Общий таймаут должен быть больше таймаута LLM + буфер
        if llm_timeout:
            actual_timeout = max(api_timeout, llm_timeout + 60, 300)  # Буфер 60 секунд, минимум 5 минут
        else:
            actual_timeout = max(api_timeout, 300)  # Минимум 5 минут
        
        with st.spinner(f"📥 Скачивание и анализ статьи... (таймаут: {actual_timeout} сек)"):
            try:
                request_data = {
                    "source": source,
                    "source_type": source_type if source_type != "auto" else None,
                    "llm_provider": llm_provider_for_timeout,
                    "model": st.session_state.get("selected_model", os.getenv("OLLAMA_MODEL", "qwen3:8b")),
                    "timeout": mcp_timeout
                }
                
                # Добавляем таймаут LLM, если указан
                if llm_timeout:
                    request_data["llm_timeout"] = llm_timeout
                
                with httpx.Client(timeout=float(actual_timeout)) as client:
                    response = client.post(
                        f"{API_BASE_URL}/api/kb/articles/parse",
                        json=request_data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        parsed_document = result.get("parsed_document", {})
                        review = result.get("review", {})
                        summary = review.get("summary", {})
                        
                        # Сохранение в session state для дальнейшей обработки
                        st.session_state.parsed_document = parsed_document
                        st.session_state.review = review
                        st.session_state.summary = summary
                        st.session_state.document_source = source
                        
                        st.success("✅ Документ успешно скачан и проанализирован!")
                        
                        # Решение библиотекаря
                        decision = review.get("decision", "needs_review")
                        reason = review.get("reason", "")
                        relevance_score = review.get("relevance_score", 0.0)
                        quality_score = review.get("quality_score", 0.0)
                        
                        st.subheader("📋 Решение библиотекаря")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if decision == "approve":
                                st.success(f"✅ **Одобрено**")
                            elif decision == "reject":
                                st.error(f"❌ **Отклонено**")
                            else:
                                st.warning(f"⚠️ **Требуется проверка**")
                        
                        with col2:
                            threshold = st.session_state.relevance_threshold
                            threshold_color = "normal" if relevance_score >= threshold else "inverse"
                            st.metric(
                                "Релевантность",
                                f"{relevance_score:.2f}",
                                delta=f"Порог: {threshold:.2f}",
                                delta_color=threshold_color
                            )
                        
                        with col3:
                            st.metric("Качество", f"{quality_score:.2f}")
                        
                        st.info(f"**Причина:** {reason}")
                        
                        # Решение администратора
                        st.markdown("---")
                        st.subheader("👤 Решение администратора")
                        
                        # Инициализация admin_decision из session_state или из решения библиотекаря
                        if "admin_decision" not in st.session_state or st.session_state.admin_decision is None:
                            st.session_state.admin_decision = decision
                        
                        admin_decision = st.radio(
                            "Ваше решение:",
                            ["approve", "reject", "needs_review"],
                            index=["approve", "reject", "needs_review"].index(st.session_state.admin_decision) if st.session_state.admin_decision in ["approve", "reject", "needs_review"] else 2,
                            format_func=lambda x: {
                                "approve": "✅ Одобрить и добавить в KB",
                                "reject": "❌ Отклонить",
                                "needs_review": "⚠️ Требуется дополнительная проверка"
                            }.get(x, x),
                            help="Вы можете переопределить решение библиотекаря"
                        )
                        
                        st.session_state.admin_decision = admin_decision
                        
                        # Предупреждение если решение переопределено
                        if admin_decision != decision:
                            if admin_decision == "approve" and decision == "reject":
                                st.warning("⚠️ Вы одобряете статью, отклоненную библиотекарем")
                            elif admin_decision == "reject" and decision == "approve":
                                st.warning("⚠️ Вы отклоняете статью, одобренную библиотекарем")
                        
                        # Предупреждение если релевантность ниже порога
                        if relevance_score < st.session_state.relevance_threshold and admin_decision == "approve":
                            st.warning(
                                f"⚠️ Релевантность ({relevance_score:.2f}) ниже установленного порога "
                                f"({st.session_state.relevance_threshold:.2f})"
                            )
                        
                        # Проверка на дублирование
                        duplicate_check = review.get("duplicate_check", {})
                        if duplicate_check.get("is_duplicate"):
                            st.warning("⚠️ **Обнаружены похожие документы в KB:**")
                            for i, similar_title in enumerate(duplicate_check.get("similar_docs", [])[:3], 1):
                                st.write(f"{i}. {similar_title}")
                        
                        # Abstract
                        abstract = review.get("abstract", "")
                        if abstract:
                            st.subheader("📝 Abstract (краткое изложение)")
                            st.info(abstract)
                        
                        st.markdown("---")
                        
                        # Отображение результатов
                        st.subheader("📄 Распарсенный документ")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**Заголовок:**", parsed_document.get("title", ""))
                            st.write("**Тип контента:**", parsed_document.get("content_type", "article"))
                            st.write("**Раздел:**", parsed_document.get("section", "unknown"))
                            st.write("**Дата:**", parsed_document.get("date", ""))
                            if parsed_document.get("author"):
                                st.write("**Автор:**", parsed_document["author"])
                        
                        with col2:
                            st.write("**Источник:**", source[:100] if len(source) > 100 else source)
                            if parsed_document.get("url"):
                                st.write("**URL:**", parsed_document["url"])
                            if parsed_document.get("tags"):
                                st.write("**Теги:**", ", ".join(parsed_document["tags"]))
                            st.write("**Изображений:**", len(parsed_document.get("images", [])))
                        
                        # Краткое изложение от агента-библиотекаря
                        st.subheader("📋 Краткое изложение (от агента-библиотекаря)")
                        
                        content_type = summary.get("content_type", "article") if summary else "article"
                        st.info(f"**Тип контента:** {content_type}")
                        
                        if summary:
                            st.markdown(summary.get("summary", ""))
                        
                        # Детали изложения в зависимости от типа контента
                        with st.expander("🔍 Детали анализа"):
                            if content_type == "article":
                                st.write("**Проблема:**", summary.get("problem", ""))
                                
                                if summary.get("symptoms"):
                                    st.write("**Симптомы:**")
                                    for symptom in summary["symptoms"]:
                                        st.write(f"- {symptom}")
                                
                                if summary.get("solutions"):
                                    st.write("**Решения:**")
                                    for i, solution in enumerate(summary["solutions"], 1):
                                        st.write(f"{i}. {solution.get('description', '')}")
                                        if solution.get("parameters"):
                                            st.write(f"   Параметры: {solution['parameters']}")
                                
                                if summary.get("printer_models"):
                                    st.write("**Принтеры:**", ", ".join(summary["printer_models"]))
                                
                                if summary.get("materials"):
                                    st.write("**Материалы:**", ", ".join(summary["materials"]))
                            
                            elif content_type == "documentation":
                                st.write("**Тип документации:**", summary.get("documentation_type", ""))
                                if summary.get("equipment_models"):
                                    st.write("**Модели оборудования:**", ", ".join(summary["equipment_models"]))
                                if summary.get("key_specifications"):
                                    st.write("**Характеристики:**")
                                    for k, v in summary["key_specifications"].items():
                                        st.write(f"- {k}: {v}")
                            
                            elif content_type == "comparison":
                                st.write("**Тип сравнения:**", summary.get("comparison_type", ""))
                                if summary.get("compared_items"):
                                    st.write("**Сравниваемые варианты:**", ", ".join(summary["compared_items"]))
                                if summary.get("key_differences"):
                                    st.write("**Ключевые отличия:**")
                                    for item, diffs in summary["key_differences"].items():
                                        st.write(f"- **{item}**: {', '.join(diffs)}")
                            
                            elif content_type == "technical":
                                st.write("**Тема:**", summary.get("topic", ""))
                                if summary.get("key_characteristics"):
                                    st.write("**Характеристики:**")
                                    for k, v in summary["key_characteristics"].items():
                                        st.write(f"- {k}: {v}")
                            
                            if summary.get("key_points"):
                                st.write("**Ключевые моменты:**")
                                for kp in summary["key_points"]:
                                    st.write(f"- {kp}")
                        
                        # Изображения из документа
                        if parsed_document.get("images"):
                            st.subheader("🖼️ Изображения из документа")
                            for i, img in enumerate(parsed_document["images"][:5], 1):  # Показываем первые 5
                                with st.expander(f"Изображение {i}: {img.get('alt', 'Без описания')}"):
                                    try:
                                        st.image(img["url"], use_container_width=True)
                                    except:
                                        st.info(f"Не удалось загрузить изображение: {img['url']}")
                                    if img.get("description"):
                                        st.caption(img["description"])
                        
                        # Рекомендации библиотекаря
                        recommendations = review.get("recommendations", [])
                        if recommendations:
                            st.subheader("💡 Рекомендации библиотекаря")
                            for rec in recommendations:
                                st.write(f"- {rec}")
                        
                        # Кнопки действий в зависимости от решения администратора
                        st.markdown("---")
                        st.subheader("🎯 Действия")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if admin_decision == "approve":
                                if st.button("✅ Добавить в KB", type="primary", use_container_width=True):
                                    # Добавление статьи в KB
                                    try:
                                        with httpx.Client(timeout=float(os.getenv("API_REQUEST_TIMEOUT", "300"))) as client:
                                            add_response = client.post(
                                                f"{API_BASE_URL}/api/kb/articles/add_from_parse",
                                                json={
                                                    "parsed_document": parsed_document,
                                                    "review": review,
                                                    "admin_decision": admin_decision,
                                                    "relevance_threshold": st.session_state.relevance_threshold
                                                },
                                                timeout=float(os.getenv("API_REQUEST_TIMEOUT", "300"))
                                            )
                                            
                                            if add_response.status_code == 200:
                                                result = add_response.json()
                                                # Сохраняем статус успеха перед rerun
                                                st.session_state.add_success_status = {
                                                    "message": "Статья успешно добавлена в KB!",
                                                    "article_id": result.get('article_id', 'unknown')
                                                }
                                                # Очистка session state (но сохраняем input_method чтобы остаться на той же странице)
                                                input_method = st.session_state.get("input_method", "")
                                                if "parsed_document" in st.session_state:
                                                    del st.session_state.parsed_document
                                                if "review" in st.session_state:
                                                    del st.session_state.review
                                                if "admin_decision" in st.session_state:
                                                    del st.session_state.admin_decision
                                                # Сохраняем метод ввода чтобы остаться на той же странице
                                                if input_method:
                                                    st.session_state.input_method = input_method
                                                st.rerun()
                                            else:
                                                error_detail = add_response.json().get('detail', add_response.text)
                                                st.error(f"❌ Ошибка добавления: {error_detail}")
                                    except Exception as e:
                                        st.error(f"❌ Ошибка подключения к API: {e}")
                            elif admin_decision == "reject":
                                st.info("📋 Документ отклонен. Он не будет добавлен в KB.")
                                if st.button("🔄 Очистить форму", use_container_width=True):
                                    if "parsed_document" in st.session_state:
                                        del st.session_state.parsed_document
                                    if "review" in st.session_state:
                                        del st.session_state.review
                                    if "admin_decision" in st.session_state:
                                        del st.session_state.admin_decision
                                    st.rerun()
                            else:  # needs_review
                                st.warning("⚠️ Требуется дополнительная проверка перед добавлением в KB")
                                if st.button("💾 Сохранить для проверки", use_container_width=True):
                                    st.info("💡 Документ сохранен в сессии. Вы можете вернуться к нему позже.")
                        
                        with col2:
                            if st.button("🔄 Сбросить решение", use_container_width=True):
                                if "parsed_document" in st.session_state:
                                    del st.session_state.parsed_document
                                if "review" in st.session_state:
                                    del st.session_state.review
                                if "admin_decision" in st.session_state:
                                    del st.session_state.admin_decision
                                st.rerun()
                    else:
                        error_detail = response.json().get('detail', response.text)
                        st.error(f"❌ Ошибка парсинга: {error_detail}")
                        
            except Exception as e:
                st.error(f"❌ Ошибка подключения к API: {e}")
                st.info("💡 Убедитесь, что FastAPI сервер запущен")

elif input_method == "📝 Ручной ввод":
    # Ручной ввод (существующая форма)
    # Не используем clear_on_submit, чтобы сохранить данные при ошибке
    with st.form("article_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            url = st.text_input("URL статьи (опционально)", placeholder="https://3dtoday.ru/...")
            section = st.selectbox(
                "Раздел",
                ["Техничка", "3D-печать", "Оборудование", "Материалы", "Применение", "Другое"]
            )
        
        with col2:
            st.info("💡 Заполните обязательные поля: заголовок и содержимое")
        
        title = st.text_input("Заголовок статьи *", placeholder="Как устранить stringing на Ender-3")
        
        content = st.text_area(
            "Содержимое статьи *",
            height=300,
            placeholder="Вставьте полный текст статьи..."
        )
        
        submitted = st.form_submit_button("🔍 Проверить и добавить в KB", use_container_width=True)
    
    # Обработка формы ручного ввода
    if submitted:
        if not title or not content:
            st.error("❌ Заполните обязательные поля: заголовок и содержимое")
        else:
            # Шаг 1: Валидация
            # Используем таймаут из настроек sidebar
            api_timeout = st.session_state.get("timeout_values", {}).get("API запросы", int(os.getenv("API_REQUEST_TIMEOUT", "300")))
            llm_timeout = None
            
            # Определяем таймаут LLM в зависимости от провайдера
            sidebar_provider = st.session_state.get("llm_provider", "ollama")
            if sidebar_provider == "ollama":
                llm_timeout = st.session_state.get("timeout_values", {}).get("LLM генерация (Ollama)", int(os.getenv("OLLAMA_TIMEOUT", "500")))
            elif sidebar_provider == "openai":
                llm_timeout = st.session_state.get("timeout_values", {}).get("LLM генерация (OpenAI)", int(os.getenv("OPENAI_TIMEOUT", "120")))
            elif sidebar_provider == "gemini":
                llm_timeout = st.session_state.get("timeout_values", {}).get("LLM генерация (OpenAI)", int(os.getenv("GEMINI_TIMEOUT", "120")))
            
            # Общий таймаут должен быть больше таймаута LLM + буфер
            if llm_timeout:
                actual_timeout = max(api_timeout, llm_timeout + 60)  # Буфер 60 секунд
            else:
                actual_timeout = max(api_timeout, 300)  # Минимум 300 секунд
            
            with st.spinner(f"🔍 Проверка релевантности статьи... (таймаут: {actual_timeout} сек)"):
                try:
                    request_data = {
                        "title": title,
                        "content": content,
                        "url": url if url else None,
                        "section": section
                    }
                    
                    # Добавляем таймаут LLM, если указан
                    if llm_timeout:
                        request_data["llm_timeout"] = llm_timeout
                    
                    with httpx.Client(timeout=float(actual_timeout)) as client:
                        response = client.post(
                            f"{API_BASE_URL}/api/kb/articles/validate",
                            json=request_data,
                            timeout=float(actual_timeout)
                        )
                        
                        if response.status_code == 200:
                            validation = response.json()
                        else:
                            error_detail = response.json().get('detail', response.text) if response.headers.get('content-type', '').startswith('application/json') else response.text
                            st.error(f"❌ Ошибка валидации: {error_detail}")
                            st.stop()
                except httpx.TimeoutException:
                    st.error(f"❌ Таймаут запроса ({actual_timeout} сек). Увеличьте таймаут в настройках sidebar или попробуйте позже.")
                    st.info("💡 Увеличьте таймаут 'API запросы' и 'LLM генерация' в настройках sidebar (слева)")
                    st.stop()
                except Exception as e:
                    st.error(f"❌ Ошибка подключения к API: {e}")
                    st.info("💡 Убедитесь, что FastAPI сервер запущен: `uvicorn backend.app.main:app --reload`")
                    st.stop()
            
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
            
            # Извлеченные метаданные
            metadata = validation.get('metadata')
            if metadata:
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
            
            # Подтверждение и добавление
            if is_relevant:
                st.markdown("---")
                
                if st.button("💾 Добавить статью в KB", type="primary", use_container_width=True):
                    with st.spinner("💾 Индексация статьи..."):
                        try:
                            with httpx.Client(timeout=120.0) as client:
                                response = client.post(
                                    f"{API_BASE_URL}/api/kb/articles/add",
                                    json={
                                        "title": title,
                                        "content": content,
                                        "url": url if url else None,
                                        "section": section
                                    }
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    # Сохраняем статус успеха перед rerun
                                    st.session_state.add_success_status = {
                                        "message": "Статья успешно добавлена в KB!",
                                        "article_id": result.get('article_id')
                                    }
                                    # Очистка формы через rerun
                                    st.rerun()
                                else:
                                    error_detail = response.json().get('detail', response.text)
                                    st.error(f"❌ Ошибка: {error_detail}")
                        except Exception as e:
                            st.error(f"❌ Ошибка подключения к API: {e}")

else:  # Импорт из JSON
    st.info("📄 Импорт из JSON будет доступен в следующей версии")
    json_input = st.text_area(
        "Вставьте JSON статьи",
        height=200,
        placeholder='{"title": "...", "content": "...", ...}'
    )
    
    if st.button("📥 Импортировать из JSON"):
        st.info("Функция импорта из JSON будет реализована позже")

# Обработка добавления распарсенного документа
if st.session_state.get("use_parsed_document") and st.session_state.get("parsed_document"):
    parsed_document = st.session_state.parsed_document
    review = st.session_state.get("review", {})
    summary = st.session_state.get("summary", {})
    
    # Используем отфильтрованный контент если есть
    filtered_content = review.get("filtered_content")
    if filtered_content:
        parsed_document["content"] = filtered_content
    
    # Валидация распарсенной статьи
    with st.spinner("🔍 Валидация распарсенной статьи..."):
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{API_BASE_URL}/api/kb/articles/validate",
                    json={
                        "title": parsed_document.get("title", ""),
                        "content": parsed_document.get("content", ""),
                        "url": parsed_document.get("url") or st.session_state.get("document_source"),
                        "section": parsed_document.get("section", "unknown")
                    }
                )
                
                if response.status_code == 200:
                    validation = response.json()
                    
                    # Отображение валидации
                    st.subheader("📊 Результаты валидации")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        relevance_score = validation.get('relevance_score', 0)
                        st.metric("Релевантность", f"{relevance_score:.2f}")
                    
                    with col2:
                        quality_score = validation.get('quality_score', 0)
                        st.metric("Качество", f"{quality_score:.2f}")
                    
                    with col3:
                        has_solutions = validation.get('has_solutions', False)
                        st.metric("Есть решения", "✅ Да" if has_solutions else "❌ Нет")
                    
                    # Если релевантна - предложить добавить
                    if validation.get('is_relevant'):
                        if st.button("💾 Добавить статью в KB", type="primary", use_container_width=True):
                            with st.spinner("💾 Индексация статьи..."):
                                try:
                                    with httpx.Client(timeout=120.0) as client:
                                        response = client.post(
                                            f"{API_BASE_URL}/api/kb/articles/add",
                                            json={
                                                "title": parsed_document.get("title", ""),
                                                "content": parsed_document.get("content", ""),
                                                "url": parsed_document.get("url") or st.session_state.get("document_source"),
                                                "section": parsed_document.get("section", "unknown")
                                            }
                                        )
                                        
                                        if response.status_code == 200:
                                            result = response.json()
                                            # Сохраняем статус успеха перед rerun
                                            st.session_state.add_success_status = {
                                                "message": "Статья успешно добавлена в KB!",
                                                "article_id": result.get('article_id')
                                            }
                                            # Очистка session state
                                            del st.session_state.use_parsed_document
                                            del st.session_state.parsed_document
                                            del st.session_state.summary
                                            del st.session_state.document_source
                                            
                                            st.rerun()
                                        else:
                                            error_detail = response.json().get('detail', response.text)
                                            st.error(f"❌ Ошибка: {error_detail}")
                                except Exception as e:
                                    st.error(f"❌ Ошибка: {e}")
                    else:
                        st.warning("⚠️ Статья не релевантна и не может быть добавлена")
                        
        except Exception as e:
            st.error(f"❌ Ошибка валидации: {e}")

    # Инструкция
    with st.expander("📖 Инструкция по использованию"):
        st.markdown("""
    ### Процесс добавления статьи:
    
    1. **Введите данные статьи**
       - URL (опционально)
       - Заголовок (обязательно)
       - Содержимое (обязательно)
       - Раздел
    
    2. **Проверка релевантности**
       - Система автоматически проверит релевантность через LLM
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
       - Статья добавляется в Qdrant через API
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

# Вкладка 2: Инструкция по тестированию
with tab2:
    st.header("🧪 Инструкция по тестированию веб-интерфейса")
    st.markdown("---")
    
    st.markdown("""
    ## 📋 План тестирования для администраторов хакатона
    
    Эта инструкция поможет вам протестировать функциональность добавления статей в базу знаний.
    """)
    
    st.subheader("📦 Тестовые материалы")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 1. URL статьи (4 шт)
        
        #### ✅ Тест 1: Simplify3D - Under-Extrusion
        **URL:** `https://www.simplify3d.com/resources/print-quality-troubleshooting/under-extrusion/`  
        **Метод:** Обычный парсинг + LLM парсинг  
        
        **Шаги:**
        1. Выберите метод "🤖 По URL (через LLM - GPT-4o/Gemini)"
        2. Вставьте URL выше
        3. Выберите провайдер: Gemini или OpenAI
        4. Нажмите "Анализировать через LLM"
        5. Проверьте результаты парсинга
        6. Одобрите и добавьте в KB
        
        ---
        
        #### ✅ Тест 2: All3DP - Layer Shifting
        **URL:** `https://all3dp.com/2/3d-print-layer-shifting-how-to-fix-it/`  
        **Метод:** LLM парсинг (рекомендуется)  
        
        **Шаги:**
        1. Выберите метод "🤖 По URL (через LLM)"
        2. Вставьте URL
        3. Выберите провайдер: Gemini или OpenAI
        4. Распарсите и проверьте результаты
        5. Добавьте в KB
        
        ---
        
        #### ✅ Тест 3: Prusa KB - Elephant's Foot
        **URL:** `https://help.prusa3d.com/article/elephants-foot_1259`  
        **Метод:** LLM парсинг  
        
        **Шаги:**
        1. Выберите метод "🤖 По URL (через LLM)"
        2. Вставьте URL
        3. Распарсите и проверьте качество метаданных
        4. Добавьте в KB
        
        ---
        
        #### ✅ Тест 4: MatterHackers - Bed Adhesion
        **URL:** `https://www.matterhackers.com/articles/3d-printer-bed-adhesion-guide`  
        **Метод:** Обычный парсинг + LLM парсинг  
        
        **Шаги:**
        1. Протестируйте оба метода парсинга
        2. Сравните результаты
        3. Добавьте лучший вариант в KB
        """)
    
    with col2:
        st.markdown("""
        ### 2. PDF документ
        
        #### ✅ Тест 5: PDF - First Layer Calibration
        **Файл:** Используйте `tools/test_data/O1A1-EN-RES.pdf` (если есть)  
        **Метод:** Загрузка файла  
        
        **Шаги:**
        1. Выберите метод "🔗 По URL/Файлу (автоматический парсинг)"
        2. Выберите "Загрузить файл"
        3. Загрузите PDF
        4. Проверьте результаты парсинга
        5. Добавьте в KB
        
        ---
        
        ### 3. Текстовый документ
        
        #### ✅ Тест 6: TXT файл - Stringing Guide
        **Файл:** `tools/test_data/test_stringing_guide.txt`  
        **Метод:** Загрузка файла  
        
        **Шаги:**
        1. Выберите метод "🔗 По URL/Файлу (автоматический парсинг)"
        2. Выберите "Загрузить файл"
        3. Загрузите `tools/test_data/test_stringing_guide.txt`
        4. Проверьте извлечение метаданных
        5. Добавьте в KB
        """)
    
    st.subheader("✅ Чек-лист проверки")
    
    st.markdown("""
    Для каждого теста проверьте:
    
    ### Парсинг:
    - [ ] Контент извлечен (минимум 500 символов)
    - [ ] Заголовок определен
    - [ ] Изображения найдены (если есть в источнике)
    - [ ] Метаданные извлечены (problem_type, printer_models, materials, solutions)
    
    ### Анализ:
    - [ ] Релевантность определена (relevance_score)
    - [ ] Качество определено (quality_score)
    - [ ] Решения извлечены (solutions с параметрами)
    
    ### Добавление в KB:
    - [ ] Статья успешно добавлена
    - [ ] Article ID получен
    - [ ] Статистика KB обновлена
    - [ ] Статья доступна для поиска
    
    ### UI:
    - [ ] Результаты отображаются корректно
    - [ ] Изображения отображаются (если есть)
    - [ ] Ошибки обрабатываются понятно
    - [ ] Прогресс отображается (для длительных операций)
    """)
    
    st.subheader("📊 Ожидаемые результаты")
    
    st.markdown("""
    После прохождения всех тестов:
    
    - **Добавлено статей:** 6-7 (4 URL + 1-2 PDF + 1 TXT)
    - **Типы проблем:** under_extrusion, layer_shifting, elephants_foot, bed_adhesion, stringing
    - **Изображения:** Должны быть проиндексированы (если есть в источниках)
    - **Покрытие:** Разные сайты, разные форматы, разные проблемы
    
    ### Проверка через скрипт:
    ```bash
    python tools/check_kb_stats.py
    ```
    
    Ожидаемый результат:
    - Статей: +6-7 к текущему количеству
    - Новые типы проблем в статистике
    - Новые модели принтеров
    - Новые материалы
    """)
    
    st.subheader("🐛 Известные проблемы и обходные пути")
    
    st.markdown("""
    ### Проблема 1: All3DP и Prusa KB не парсятся обычным парсером
    **Решение:** Использовать LLM парсинг (`parse_with_llm`)
    
    ### Проблема 2: Таймауты при парсинге больших страниц
    **Решение:** Увеличить таймауты в UI (настройки в sidebar)
    
    ### Проблема 3: Изображения не отображаются в UI
    **Решение:** Проверить логи, возможно требуется дополнительная настройка
    
    ### Проблема 4: Вылет в начало после добавления
    **Решение:** Исправлено - теперь остается на той же странице
    """)
    
    st.subheader("💡 Советы для тестирования")
    
    st.markdown("""
    1. **Начните с простых тестов:** Simplify3D обычно парсится лучше всего
    2. **Используйте LLM парсинг для проблемных сайтов:** All3DP, Prusa KB
    3. **Проверяйте таймауты:** Увеличьте их если операции занимают много времени
    4. **Сохраняйте логи:** Могут понадобиться для отладки
    5. **Проверяйте статистику:** После каждого добавления проверяйте `check_kb_stats.py`
    6. **Время на тестирование:** Ориентировочно 60-85 минут на все тесты
    """)
    
    st.subheader("🔗 Полезные ссылки")
    
    st.markdown("""
    - **API документация:** http://localhost:8000/docs
    - **Статистика KB:** `python tools/check_kb_stats.py`
    - **Полный план тестирования:** `tools/TESTING_PLAN_LIBRARIAN_UI.md`
    - **Чек-лист UI:** `tools/UI_TESTING_CHECKLIST.md`
    """)
    
    st.markdown("---")
    st.success("🚀 Удачи в тестировании! Если возникнут проблемы, проверьте логи или обратитесь к документации.")

