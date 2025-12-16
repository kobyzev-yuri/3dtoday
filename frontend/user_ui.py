"""
Streamlit интерфейс для пользователей (диагностика проблем)
Работает через FastAPI
"""

import streamlit as st
import httpx
from typing import List, Dict, Any, Optional
import json
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Настройка логирования для отладки
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Удаляем существующие handlers, чтобы избежать дублирования
if logger.handlers:
    logger.handlers.clear()

# Форматтер с подробной информацией
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Handler для файла
file_handler = logging.FileHandler(
    LOG_DIR / 'user_ui.log',
    encoding='utf-8',
    mode='a'
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Handler для консоли (опционально, можно убрать для production)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Загрузка конфигурации
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / "config.env")

# Конфигурация API
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
logger.info(f"=== USER UI PAGE LOADED ===")
logger.info(f"API_BASE_URL: {API_BASE_URL}")

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

# Загрузка списков материалов и принтеров из KB
@st.cache_data(ttl=300)  # Кэш на 5 минут
def load_metadata_from_kb():
    """
    Загрузка уникальных материалов и принтеров из KB
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{API_BASE_URL}/api/kb/metadata/unique-values")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Loaded metadata: {len(data.get('materials', []))} materials, {len(data.get('printer_models', []))} printers")
                return data
            else:
                logger.warning(f"Failed to load metadata: {response.status_code}")
                return {"materials": [], "printer_models": []}
    except Exception as e:
        logger.error(f"Error loading metadata from KB: {e}")
        # Возвращаем дефолтные значения при ошибке
        return {
            "materials": ["PLA", "PETG", "ABS", "TPU"],
            "printer_models": []
        }

# Загружаем метаданные
try:
    metadata = load_metadata_from_kb()
    available_materials = [""] + metadata.get("materials", ["PLA", "PETG", "ABS", "TPU"])
    available_printers = [""] + metadata.get("printer_models", [])
except Exception as e:
    logger.error(f"Error loading metadata: {e}")
    available_materials = ["", "PLA", "PETG", "ABS", "TPU"]
    available_printers = [""]

# Боковая панель с контекстом пользователя
with st.sidebar:
    st.header("⚙️ Контекст")
    
    st.subheader("Информация о вашем принтере")
    
    # Модель принтера - selectbox с актуальными значениями из KB
    current_printer = st.session_state.user_context.get("printer_model", "")
    printer_index = 0
    if current_printer and current_printer in available_printers:
        printer_index = available_printers.index(current_printer)
    elif current_printer:
        # Если принтер не в списке, добавляем его в начало
        available_printers.insert(1, current_printer)
        printer_index = 1
    
    printer_model = st.selectbox(
        "Модель принтера",
        available_printers,
        index=printer_index,
        help="Выберите модель принтера из базы знаний или введите свою"
    )
    
    # Если выбран пустой вариант, но есть текст в контексте, используем text_input
    if printer_model == "" and current_printer and current_printer not in available_printers:
        printer_model = st.text_input(
            "Или введите модель принтера вручную",
            value=current_printer,
            key="printer_model_input",
            placeholder="Ender-3, Anycubic Kobra, etc."
        )
    
    # Материал - selectbox с актуальными значениями из KB
    current_material = st.session_state.user_context.get("material", "")
    material_index = 0
    if current_material and current_material in available_materials:
        material_index = available_materials.index(current_material)
    
    material = st.selectbox(
        "Материал",
        available_materials,
        index=material_index,
        help="Выберите материал из базы знаний"
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
    
    # Выбор LLM провайдера и модели
    st.subheader("🤖 LLM для диагностики")
    
    # Инициализация session state для LLM настроек
    if "llm_provider" not in st.session_state:
        st.session_state.llm_provider = os.getenv("LLM_PROVIDER", "ollama")
    if "llm_model" not in st.session_state:
        st.session_state.llm_model = None
    
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
        index=["openai", "ollama", "gemini"].index(st.session_state.llm_provider) if st.session_state.llm_provider in ["openai", "ollama", "gemini"] else ["openai", "ollama", "gemini"].index(default_provider) if default_provider in ["openai", "ollama", "gemini"] else 1,
        format_func=lambda x: {
            "openai": f"GPT-4o ({'ProxyAPI.ru' if uses_proxyapi_openai else 'OpenAI'})",
            "ollama": "Ollama",
            "gemini": f"Gemini ({'ProxyAPI.ru' if uses_proxyapi_gemini else 'Google'})"
        }.get(x, x),
        help="Выберите провайдер LLM для диагностики",
        key="llm_provider_select"
    )
    st.session_state.llm_provider = llm_provider
    
    # Выбор модели в зависимости от провайдера
    selected_model = None
    if llm_provider == "openai":
        openai_models = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
        current_model = st.session_state.llm_model or default_openai_model
        selected_model = st.selectbox(
            "Модель OpenAI:",
            openai_models,
            index=openai_models.index(current_model) if current_model in openai_models else 0,
            key="openai_model_select"
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
                        current_model = st.session_state.llm_model or default_ollama_model
                        if current_model not in preferred:
                            current_model = preferred[0] if preferred else available_models[0]
                        
                        selected_model = st.selectbox(
                            "Модель Ollama:",
                            preferred if preferred else available_models,
                            index=preferred.index(current_model) if current_model in preferred else 0,
                            help=f"Доступно моделей: {len(available_models)}",
                            key="ollama_model_select"
                        )
                    else:
                        selected_model = st.text_input(
                            "Модель Ollama:",
                            value=st.session_state.llm_model or default_ollama_model,
                            help="Модели не найдены. Введите название модели вручную",
                            key="ollama_model_input"
                        )
                else:
                    selected_model = st.text_input(
                        "Модель Ollama:",
                        value=st.session_state.llm_model or default_ollama_model,
                        help="Не удалось получить список моделей. Введите название модели вручную",
                        key="ollama_model_input"
                    )
        except Exception as e:
            selected_model = st.text_input(
                "Модель Ollama:",
                value=st.session_state.llm_model or default_ollama_model,
                help=f"Ошибка получения моделей: {e}. Введите название модели вручную",
                key="ollama_model_input"
            )
    else:  # gemini
        gemini_models = ["gemini-3-pro-preview", "gemini-pro", "gemini-1.5-pro"]
        current_model = st.session_state.llm_model or default_gemini_model
        selected_model = st.selectbox(
            "Модель Gemini:",
            gemini_models,
            index=gemini_models.index(current_model) if current_model in gemini_models else 0,
            key="gemini_model_select"
        )
    
    st.session_state.llm_model = selected_model
    
    st.markdown("---")
    
    # Настройки таймаутов
    st.subheader("⏱️ Таймауты (сек)")
    
    # Инициализация session state для таймаутов
    if "timeout_values" not in st.session_state:
        st.session_state.timeout_values = {}
    
    # Автоматическое определение таймаута для Ollama в зависимости от модели
    ollama_timeout_default = int(os.getenv("OLLAMA_TIMEOUT", "100"))
    if st.session_state.get("llm_provider") == "ollama" and st.session_state.get("llm_model"):
        selected_model = st.session_state.get("llm_model", "")
        # Определяем, тяжелая ли модель
        heavy_models = ["qwen3:8b", "qwen3", "llama3.1:70b", "llama3:70b"]
        if any(heavy in selected_model.lower() for heavy in ["qwen3:8b", "qwen3", "70b"]):
            ollama_timeout_default = int(os.getenv("OLLAMA_TIMEOUT_HEAVY", "900"))
        else:
            ollama_timeout_default = int(os.getenv("OLLAMA_TIMEOUT_LIGHT", "100"))
    
    default_timeouts = {
        "Диагностика (общий)": int(os.getenv("DIAGNOSTIC_TIMEOUT", os.getenv("API_REQUEST_TIMEOUT", "300"))),
        "LLM генерация (Ollama)": ollama_timeout_default,
        "LLM генерация (OpenAI)": int(os.getenv("OPENAI_TIMEOUT", "600")),
        "LLM генерация (Gemini)": int(os.getenv("GEMINI_TIMEOUT", "600")),
        "RAG поиск": int(os.getenv("RAG_SEARCH_TIMEOUT", "30")),
        "API запросы": int(os.getenv("API_REQUEST_TIMEOUT", "300"))
    }
    
    timeout_values = {}
    for timeout_name, default_value in default_timeouts.items():
        # Используем сохраненное значение или дефолтное
        # Для Ollama автоматически определяем таймаут только при первом выборе модели
        if timeout_name == "LLM генерация (Ollama)" and st.session_state.get("llm_provider") == "ollama":
            current_model = st.session_state.get("llm_model", "")
            saved_timeout = st.session_state.timeout_values.get(timeout_name)
            saved_model = st.session_state.get("_last_ollama_model_for_timeout", "")
            
            # Если модель изменилась И значение не было установлено пользователем явно
            if current_model and current_model != saved_model:
                is_heavy = any(heavy in current_model.lower() for heavy in ["qwen3:8b", "qwen3", "70b"])
                expected_timeout = int(os.getenv("OLLAMA_TIMEOUT_HEAVY", "900")) if is_heavy else int(os.getenv("OLLAMA_TIMEOUT_LIGHT", "100"))
                # Устанавливаем автоматически только если значение не было сохранено пользователем
                if saved_timeout is None:
                    current_value = expected_timeout
                    st.session_state["_last_ollama_model_for_timeout"] = current_model
                else:
                    # Сохраняем значение пользователя
                    current_value = saved_timeout
            else:
                # Используем сохраненное значение или дефолтное
                current_value = saved_timeout if saved_timeout is not None else default_value
        else:
            current_value = st.session_state.timeout_values.get(timeout_name, default_value)
        
        timeout_values[timeout_name] = st.number_input(
            timeout_name,
            min_value=5,
            max_value=1800,  # До 30 минут для сложных операций
            value=current_value,
            step=5,
            help=f"Таймаут для {timeout_name.lower()} (по умолчанию: {default_value} сек)",
            key=f"timeout_{timeout_name}"
        )
    
    # Автоматическая синхронизация: общий таймаут должен быть >= таймауту LLM
    llm_provider = st.session_state.get("llm_provider", "")
    if llm_provider:
        llm_timeout_key = f"LLM генерация ({'Ollama' if llm_provider == 'ollama' else 'OpenAI' if llm_provider == 'openai' else 'Gemini'})"
        llm_timeout = timeout_values.get(llm_timeout_key, 300)
        diagnostic_timeout = timeout_values.get("Диагностика (общий)", 300)
        
        # Если общий таймаут меньше таймаута LLM, автоматически увеличиваем
        if diagnostic_timeout < llm_timeout:
            timeout_values["Диагностика (общий)"] = llm_timeout + 60  # Добавляем 60 сек запаса
            st.info(f"💡 Общий таймаут автоматически увеличен до {timeout_values['Диагностика (общий)']} сек (таймаут LLM: {llm_timeout} сек)")
    
    # Сохранение в session state
    # Примечание: значения виджетов автоматически сохраняются Streamlit через key
    st.session_state.timeout_values = timeout_values
    
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

# Загрузка релевантных примеров из KB
@st.cache_data(ttl=600)  # Кэш на 10 минут
def load_relevant_examples(candidate_queries=None):
    """
    Загрузка релевантных примеров из KB
    """
    try:
        # Дефолтные примеры для проверки
        default_candidates = [
            "Ищу тренажеры для обучения студентов-медиков",
            "У меня появляются ниточки между деталями при печати PLA на Ender-3",
            "Печать отслаивается от стола при печати PETG",
            "Трещины в слоях при печати ABS на высоких температурах",
            "Недозаполнение при печати сложных моделей",
            "Проблемы с первым слоем на стеклянном столе",
            "Как настроить retraction для уменьшения stringing",
            "Печать деформируется при охлаждении"
        ]
        
        candidates = candidate_queries if candidate_queries else default_candidates
        candidates_str = ",".join(candidates)
        
        # Получаем таймаут для загрузки примеров из настроек
        examples_timeout = 15.0
        if "timeout_values" in st.session_state:
            examples_timeout = float(st.session_state.timeout_values.get("RAG поиск", 15.0))
        
        with httpx.Client(timeout=examples_timeout) as client:
            response = client.get(
                f"{API_BASE_URL}/api/kb/examples/relevant",
                params={
                    "candidate_queries": candidates_str,
                    "limit": 8,
                    "min_score": 0.3
                }
            )
            if response.status_code == 200:
                data = response.json()
                examples = [ex["query"] for ex in data.get("examples", [])]
                logger.info(f"Loaded {len(examples)} relevant examples from KB")
                return examples
            else:
                logger.warning(f"Failed to load relevant examples: {response.status_code}")
                # Возвращаем дефолтные примеры при ошибке
                return default_candidates
    except Exception as e:
        logger.error(f"Error loading relevant examples: {e}")
        # Возвращаем дефолтные примеры при ошибке
        return [
            "У меня появляются ниточки между деталями при печати PLA на Ender-3",
            "Печать отслаивается от стола при печати PETG",
            "Трещины в слоях при печати ABS на высоких температурах",
            "Недозаполнение при печати сложных моделей",
            "Проблемы с первым слоем на стеклянном столе",
            "Как настроить retraction для уменьшения stringing",
            "Печать деформируется при охлаждении"
        ]

# Примеры успешных запросов
st.subheader("📋 Примеры успешных запросов")
st.caption("💡 Примеры проверены на релевантность в базе знаний")

# Загружаем релевантные примеры
try:
    example_queries = load_relevant_examples()
except Exception as e:
    logger.error(f"Error loading examples: {e}")
    # Fallback на дефолтные примеры
    example_queries = [
        "У меня появляются ниточки между деталями при печати PLA на Ender-3",
        "Печать отслаивается от стола при печати PETG",
        "Трещины в слоях при печати ABS на высоких температурах"
    ]

# Отображение примеров в виде кнопок
cols = st.columns(4)
for idx, example in enumerate(example_queries):
    col_idx = idx % 4
    if cols[col_idx].button(f"📌 {example[:40]}..." if len(example) > 40 else f"📌 {example}", 
                            key=f"example_{idx}", 
                            use_container_width=True):
        logger.info(f"Example selected: {repr(example)}")
        st.session_state.selected_example = example
        st.rerun()

# Применение выбранного примера
if "selected_example" in st.session_state:
    st.info(f"💡 Выбран пример: **{st.session_state.selected_example}**")
    if st.button("✖️ Очистить пример"):
        logger.info(f"Example cleared: {repr(st.session_state.selected_example)}")
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
    
    # Логирование состояния формы при каждом рендере
    logger.debug(f"Form rendered. submitted={submitted}, query={repr(query)}, selected_example={st.session_state.get('selected_example')}")

# Отладочная информация
if st.session_state.get("debug_mode", False):
    with st.expander("🔍 Отладочная информация"):
        st.write(f"**submitted:** {submitted}")
        st.write(f"**query:** {repr(query)}")
        st.write(f"**query.strip():** {repr(query.strip() if query else '')}")
        st.write(f"**selected_example:** {st.session_state.get('selected_example', 'None')}")
        st.write(f"**session_state keys:** {list(st.session_state.keys())}")

# Обработка запроса
if submitted:
    # Логирование для отладки
    logger.debug(f"=== FORM SUBMITTED ===")
    logger.debug(f"query (raw): {repr(query)}")
    logger.debug(f"selected_example: {st.session_state.get('selected_example')}")
    logger.debug(f"session_state keys: {list(st.session_state.keys())}")
    
    # Нормализация query - убираем пробелы
    query = query.strip() if query else ""
    logger.debug(f"query (after strip): {repr(query)}")
    
    # Если query пустой, но есть selected_example, используем его
    if not query and "selected_example" in st.session_state:
        query = st.session_state.selected_example
        logger.debug(f"Using selected_example as query: {repr(query)}")
    
    # Очищаем выбранный пример после использования
    if "selected_example" in st.session_state:
        del st.session_state.selected_example
        logger.debug("selected_example deleted from session_state")
    
    if query:
        logger.info(f"Processing diagnostic request: {repr(query[:100])}...")
        # Добавление запроса в историю
        st.session_state.conversation_history.append({
            "role": "user",
            "content": query
        })
    
        # Подготовка запроса к API
        # Фильтруем историю, оставляя только role и content (строки)
        filtered_history = []
        for msg in st.session_state.conversation_history[:-1]:  # Без текущего запроса
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                filtered_history.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Получаем таймаут для LLM из настроек
        # ВАЖНО: Берем значение напрямую из ключа number_input (самое актуальное)
        llm_timeout = None
        if st.session_state.get("llm_provider") == "ollama":
            # Сначала пробуем получить из ключа number_input (самое актуальное значение)
            llm_timeout = st.session_state.get("timeout_LLM генерация (Ollama)")
            # Если нет, берем из timeout_values
            if llm_timeout is None:
                llm_timeout = st.session_state.timeout_values.get("LLM генерация (Ollama)")
            # Если все еще нет, используем дефолтное значение на основе модели
            if llm_timeout is None:
                current_model = st.session_state.get("llm_model", "")
                if any(heavy in current_model.lower() for heavy in ["qwen3:8b", "qwen3", "70b"]):
                    llm_timeout = int(os.getenv("OLLAMA_TIMEOUT_HEAVY", "900"))
                else:
                    llm_timeout = int(os.getenv("OLLAMA_TIMEOUT_LIGHT", "100"))
        elif st.session_state.get("llm_provider") == "openai":
            llm_timeout = st.session_state.get("timeout_LLM генерация (OpenAI)") or st.session_state.timeout_values.get("LLM генерация (OpenAI)")
        elif st.session_state.get("llm_provider") == "gemini":
            llm_timeout = st.session_state.get("timeout_LLM генерация (Gemini)") or st.session_state.timeout_values.get("LLM генерация (Gemini)")
        
        # Логируем для отладки
        logger.debug(f"LLM timeout для {st.session_state.get('llm_provider')}: {llm_timeout} (из ключа: {st.session_state.get('timeout_LLM генерация (Ollama)' if st.session_state.get('llm_provider') == 'ollama' else 'timeout_LLM генерация (OpenAI)' if st.session_state.get('llm_provider') == 'openai' else 'timeout_LLM генерация (Gemini)')})")
        
        request_data = {
            "query": query,
            "printer_model": st.session_state.user_context.get("printer_model"),
            "material": st.session_state.user_context.get("material"),
            "problem_type": st.session_state.user_context.get("problem_type"),
            "conversation_history": filtered_history,
            "llm_provider": st.session_state.get("llm_provider"),
            "llm_model": st.session_state.get("llm_model"),
            "llm_timeout": llm_timeout
        }
        logger.debug(f"Sending request to {API_BASE_URL}/api/diagnose")
        logger.debug(f"Request data: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
        
        # Получаем таймаут из настроек
        # Автоматически синхронизируем с таймаутом LLM
        llm_provider = st.session_state.get("llm_provider", "")
        if llm_provider and llm_timeout:
            diagnostic_timeout_base = float(st.session_state.timeout_values.get(
                "Диагностика (общий)", 
                DIAGNOSTIC_TIMEOUT
            ))
            # Общий таймаут должен быть >= таймауту LLM + запас
            diagnostic_timeout = max(diagnostic_timeout_base, float(llm_timeout) + 60)
        else:
            diagnostic_timeout = float(st.session_state.timeout_values.get(
                "Диагностика (общий)", 
                DIAGNOSTIC_TIMEOUT
            ))
        
        with st.spinner(f"🔍 Анализ проблемы и поиск решений... (это может занять до {int(diagnostic_timeout)} секунд)"):
            try:
                with httpx.Client(timeout=diagnostic_timeout) as client:
                    response = client.post(
                        f"{API_BASE_URL}/api/diagnose",
                        json=request_data,
                        timeout=diagnostic_timeout
                    )
                    
                    logger.debug(f"Response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        diagnostic = response.json()
                        logger.info(f"Diagnostic received successfully. Answer length: {len(diagnostic.get('answer', ''))}")
                        logger.debug(f"Diagnostic response: {json.dumps(diagnostic, ensure_ascii=False, indent=2)}")
                    elif response.status_code == 503:
                        # Сервис недоступен (LLM не запущен)
                        error_detail = response.json().get('detail', response.text) if response.headers.get('content-type', '').startswith('application/json') else response.text
                        logger.error(f"LLM service unavailable (503): {error_detail}")
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
                        logger.error(f"API error ({response.status_code}): {error_detail}")
                        st.error(f"❌ Ошибка API: {error_detail}")
                        st.stop()
            except httpx.TimeoutException as e:
                logger.error(f"Request timeout: {str(e)}")
                st.error(f"⏱️ Превышено время ожидания ответа ({int(diagnostic_timeout)} секунд)")
                st.warning("💡 Поиск в базе знаний и генерация ответа могут занимать много времени.")
                st.info("**Рекомендации:**")
                st.markdown(f"""
                - Убедитесь, что FastAPI сервер запущен: `uvicorn backend.app.main:app --reload`
                - Проверьте, что LLM сервис (Ollama/OpenAI) работает корректно
                - Попробуйте упростить запрос или указать больше контекста (модель принтера, материал)
                - **Увеличьте таймаут в настройках выше** (текущий: {int(diagnostic_timeout)} сек)
                - Или увеличьте таймаут в `config.env`: `DIAGNOSTIC_TIMEOUT=600` (10 минут)
                """)
                st.stop()
            except httpx.ConnectError as e:
                logger.error(f"Connection error: {str(e)}")
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
                logger.exception(f"Unexpected error during diagnostic request: {error_msg}")
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
                    st.markdown(f"""
                    - Убедитесь, что FastAPI сервер запущен: `uvicorn backend.app.main:app --reload`
                    - Проверьте, что LLM сервис (Ollama/OpenAI) работает корректно
                    - Попробуйте упростить запрос или указать больше контекста
                    - **Увеличьте таймаут в настройках выше** (текущий: {int(diagnostic_timeout)} сек)
                    - Или увеличьте таймаут в `config.env`: `DIAGNOSTIC_TIMEOUT=600`
                    """)
                    st.stop()
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
                    st.stop()
                else:
                    st.error(f"❌ Ошибка API: {error_msg}")
                    st.info("**💡 Убедитесь, что:**")
                    st.markdown("""
                    - FastAPI сервер запущен: `uvicorn backend.app.main:app --reload`
                    - Сервер доступен по адресу из `API_BASE_URL` в `config.env`
                    - Проверьте логи сервера для получения дополнительной информации
                    """)
                    st.stop()
        
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
        logger.info("Diagnostic completed, rerunning page")
        st.rerun()
    else:
        # Если форма отправлена, но query пустой
        logger.warning(f"Form submitted but query is empty. submitted={submitted}, query={repr(query)}")
        st.warning("⚠️ Пожалуйста, введите описание проблемы перед отправкой формы.")
        st.info("💡 Вы можете выбрать пример из списка выше или ввести свой запрос вручную.")

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



