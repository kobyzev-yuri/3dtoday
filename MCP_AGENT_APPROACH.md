# Подход MCP Agent для проекта 3dtoday

## 🎯 Анализ проекта `../mcp/`

### Архитектура MCP (Model Context Protocol)

**Ключевая идея:** Разделение инструментов (tools) и агента (agent) через протокол MCP

```
┌─────────────────────────────────────┐
│  MCP Server (mcp_server_res.py)     │
│  - Определяет инструменты (@mcp.tool)│
│  - Определяет ресурсы (@mcp.resource)│
│  - Определяет промпты (@mcp.prompt)  │
│  - Декларативный подход              │
└─────────────────────────────────────┘
           │ (stdio transport)
           ▼
┌─────────────────────────────────────┐
│  MCP Client (mcp_client_res.py)    │
│  - Загружает инструменты            │
│  - Создает LangGraph агента         │
│  - Управляет потоком                │
│  - Автоматическое использование     │
└─────────────────────────────────────┘
```

### Преимущества подхода:

1. **Декларативность**
   - Инструменты определяются через декораторы `@mcp.tool()`
   - Чистый код без сложной логики

2. **Разделение ответственности**
   - Сервер: определение инструментов
   - Клиент: управление агентом
   - Легко тестировать и поддерживать

3. **Автоматическая интеграция**
   - `load_mcp_tools(session)` автоматически загружает инструменты
   - LangGraph автоматически решает, когда вызывать инструменты

4. **Расширяемость**
   - Легко добавлять новые инструменты
   - Поддержка ресурсов и промптов
   - Модульная архитектура

---

## 🔄 Адаптация для проекта 3dtoday

### Архитектура с MCP:

```
┌─────────────────────────────────────────┐
│  KB MCP Server (kb_mcp_server.py)       │
│  @mcp.tool()                             │
│  - search_kb_articles()                 │
│  - get_article_by_id()                  │
│  - add_article_to_kb()                  │
│  - generate_qa_from_article()           │
│  - validate_article_relevance()         │
│  @mcp.resource()                         │
│  - kb_statistics()                      │
│  - article_templates()                  │
│  @mcp.prompt()                           │
│  - diagnostic_prompt()                  │
└─────────────────────────────────────────┘
           │ (stdio transport)
           ▼
┌─────────────────────────────────────────┐
│  Diagnostic MCP Client                  │
│  (diagnostic_mcp_client.py)              │
│  - LangGraph агент                      │
│  - Автоматическое использование KB      │
│  - Управление диалогом                  │
└─────────────────────────────────────────┘
```

---

## 📋 Реализация для 3dtoday

### 1. KB MCP Server (`kb_mcp_server.py`)

```python
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
from mcp.server.fastmcp.prompts.base import Message
from typing import List, Dict, Any
import json

mcp = FastMCP("KB3DToday")

# ========== TOOLS ==========

@mcp.tool()
def search_kb_articles(
    query: str,
    problem_type: str = None,
    printer_model: str = None,
    material: str = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Поиск статей в KB по запросу с фильтрацией по метаданным.
    
    Args:
        query: Текстовый запрос для поиска
        problem_type: Тип проблемы (stringing, warping, etc.)
        printer_model: Модель принтера (Ender-3, etc.)
        material: Материал (PLA, PETG, etc.)
        limit: Максимальное количество результатов
    
    Returns:
        Список релевантных статей с метаданными
    """
    # Используем RAG для поиска
    from backend.app.services.rag import RAGService
    rag = RAGService()
    
    filters = {}
    if problem_type:
        filters["problem_type"] = problem_type
    if printer_model:
        filters["printer_models"] = [printer_model]
    if material:
        filters["materials"] = [material]
    
    results = rag.search(query, filters=filters, limit=limit)
    
    return {
        "articles": [
            {
                "id": r["id"],
                "title": r["title"],
                "summary": r.get("summary", ""),
                "relevance_score": r.get("score", 0.0),
                "problem_type": r.get("problem_type"),
                "printer_models": r.get("printer_models", []),
                "materials": r.get("materials", []),
                "solutions": r.get("solutions", [])
            }
            for r in results
        ],
        "count": len(results)
    }

@mcp.tool()
def get_article_by_id(article_id: str) -> Dict[str, Any]:
    """
    Получить полную статью по ID.
    
    Args:
        article_id: ID статьи в KB
    
    Returns:
        Полная информация о статье
    """
    from backend.app.services.vector_db import VectorDBService
    db = VectorDBService()
    
    article = db.get_article(article_id)
    
    if not article:
        return {"error": f"Article {article_id} not found"}
    
    return {
        "id": article["id"],
        "title": article["title"],
        "content": article["content"],
        "url": article.get("url"),
        "problem_type": article.get("problem_type"),
        "printer_models": article.get("printer_models", []),
        "materials": article.get("materials", []),
        "solutions": article.get("solutions", []),
        "symptoms": article.get("symptoms", [])
    }

@mcp.tool()
def validate_article_relevance(
    title: str,
    content: str,
    url: str = None
) -> Dict[str, Any]:
    """
    Валидация релевантности статьи для KB.
    
    Args:
        title: Заголовок статьи
        content: Содержимое статьи
        url: URL статьи (опционально)
    
    Returns:
        Результат валидации с оценками и рекомендациями
    """
    from backend.app.agents.kb_curator import KBCuratorAgent
    from backend.app.services.llm_client import get_llm_client
    
    llm_client = get_llm_client()
    curator = KBCuratorAgent(llm_client, None)  # Без vector_db для валидации
    
    parsed_article = {
        "url": url or "",
        "title": title,
        "content": content,
        "section": "unknown",
        "date": ""
    }
    
    # Используем только валидацию (без индексации)
    validation = await curator.content_validator.validate_content(parsed_article)
    metadata = await curator.metadata_extractor.extract_metadata(parsed_article)
    
    return {
        "valid": validation["valid"],
        "relevance_score": validation.get("relevance_score", 0.0),
        "quality_score": validation.get("quality_score", 0.0),
        "has_solutions": validation.get("has_solutions", False),
        "problem_type": metadata.get("problem_type"),
        "printer_models": metadata.get("printer_models", []),
        "materials": metadata.get("materials", []),
        "issues": validation.get("issues", []),
        "recommendations": validation.get("recommendations", [])
    }

@mcp.tool()
def generate_qa_from_article(article_id: str) -> Dict[str, Any]:
    """
    Генерация Q/A пар из статьи.
    
    Args:
        article_id: ID статьи в KB
    
    Returns:
        Список сгенерированных Q/A пар
    """
    from backend.app.services.vector_db import VectorDBService
    from backend.app.agents.kb_curator import KBCuratorAgent
    from backend.app.services.llm_client import get_llm_client
    
    db = VectorDBService()
    article = db.get_article(article_id)
    
    if not article:
        return {"error": f"Article {article_id} not found"}
    
    llm_client = get_llm_client()
    curator = KBCuratorAgent(llm_client, None)
    
    metadata = {
        "problem_type": article.get("problem_type"),
        "printer_models": article.get("printer_models", []),
        "materials": article.get("materials", []),
        "solutions": article.get("solutions", [])
    }
    
    qa_pairs = await curator.qa_generator.generate_qa_pairs(article, metadata)
    
    return {
        "article_id": article_id,
        "qa_pairs": qa_pairs,
        "count": len(qa_pairs)
    }

@mcp.tool()
def add_article_to_kb(
    title: str,
    content: str,
    url: str,
    problem_type: str = None,
    printer_models: List[str] = None,
    materials: List[str] = None
) -> Dict[str, Any]:
    """
    Добавление статьи в KB (с автоматической валидацией и обработкой).
    
    Args:
        title: Заголовок статьи
        content: Содержимое статьи
        url: URL статьи
        problem_type: Тип проблемы (опционально, будет извлечен автоматически)
        printer_models: Модели принтеров (опционально)
        materials: Материалы (опционально)
    
    Returns:
        Результат добавления с ID статьи и Q/A парами
    """
    from backend.app.agents.kb_curator import KBCuratorAgent
    from backend.app.services.llm_client import get_llm_client
    from backend.app.services.vector_db import VectorDBService
    
    llm_client = get_llm_client()
    vector_db = VectorDBService()
    curator = KBCuratorAgent(llm_client, vector_db)
    
    parsed_article = {
        "url": url,
        "title": title,
        "content": content,
        "section": "unknown",
        "date": ""
    }
    
    # Обработка через KB Curator Agent
    result = await curator.process_article(parsed_article)
    
    if not result["accepted"]:
        return {
            "success": False,
            "error": result["rejection_reason"],
            "validation": result.get("validation", {})
        }
    
    # Индексация в KB
    success = await curator.index_to_kb(result)
    
    if not success:
        return {
            "success": False,
            "error": "Failed to index article in KB"
        }
    
    return {
        "success": True,
        "article_id": result["article"]["article_id"],
        "qa_count": len(result["qa_pairs"]),
        "relevance_score": result["validation"]["relevance_score"]
    }

# ========== RESOURCES ==========

@mcp.resource("kb://statistics")
def kb_statistics() -> List[str]:
    """
    Статистика KB: количество статей, Q/A пар, покрытие проблем.
    """
    from backend.app.services.vector_db import VectorDBService
    db = VectorDBService()
    
    stats = db.get_statistics()
    
    return [
        f"Всего статей: {stats.get('articles_count', 0)}",
        f"Всего Q/A пар: {stats.get('qa_count', 0)}",
        f"Проблем: {stats.get('problems_count', 0)}",
        f"Принтеров: {stats.get('printers_count', 0)}",
        f"Материалов: {stats.get('materials_count', 0)}"
    ]

@mcp.resource("kb://templates/article")
def article_templates() -> List[str]:
    """
    Шаблоны для структурирования статей.
    """
    return [
        "Шаблон статьи о проблеме:",
        "1. Описание проблемы",
        "2. Симптомы",
        "3. Причины",
        "4. Решения с параметрами",
        "5. Рекомендации"
    ]

# ========== PROMPTS ==========

@mcp.prompt(
    name="diagnostic_prompt",
    description="Промпт для диагностики проблемы 3D-печати"
)
def diagnostic_prompt(
    user_query: str,
    printer_model: str = None,
    material: str = None,
    has_image: bool = False
) -> List[Message]:
    """
    Генерирует промпт для диагностики проблемы на основе запроса пользователя.
    """
    prompt_text = f"""
Ты - эксперт по диагностике проблем 3D-печати.

ЗАПРОС ПОЛЬЗОВАТЕЛЯ: {user_query}
"""
    
    if printer_model:
        prompt_text += f"\nМОДЕЛЬ ПРИНТЕРА: {printer_model}"
    
    if material:
        prompt_text += f"\nМАТЕРИАЛ: {material}"
    
    if has_image:
        prompt_text += "\n\nПОЛЬЗОВАТЕЛЬ ПРИЛОЖИЛ ФОТО ДЕФЕКТА. Проанализируй изображение."
    
    prompt_text += """

ИСПОЛЬЗУЙ ИНСТРУМЕНТЫ:
1. search_kb_articles() - для поиска релевантных статей
2. get_article_by_id() - для получения полной информации о статье

ЗАДАЧА:
1. Найди релевантные статьи в KB
2. Проанализируй информацию
3. Дай конкретные рекомендации с параметрами
4. Если информации недостаточно - задай уточняющие вопросы

ОТВЕТ ДОЛЖЕН БЫТЬ:
- Конкретным (с параметрами: температура, скорость, retraction)
- Структурированным (проблема → решение → параметры)
- Ссылками на источники из KB
"""
    
    return [Message(role="user", content=TextContent(type="text", text=prompt_text))]

# ========== RUN SERVER ==========

if __name__ == "__main__":
    print("Starting KB MCP Server for 3dtoday...")
    mcp.run(transport="stdio")
```

### 2. Diagnostic MCP Client (`diagnostic_mcp_client.py`)

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import tools_condition, ToolNode
from typing import Annotated, TypedDict
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.schema import HumanMessage
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Настройка клиента (используем ProxyAPI из config.env)
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1"),
)

# MCP сервер
server_params = StdioServerParameters(
    command="python",
    args=["kb_mcp_server.py"]
)

# Состояние агента
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

async def create_diagnostic_agent(session):
    """Создание диагностического агента с инструментами KB"""
    
    # Загрузка инструментов из MCP сервера
    tools = await load_mcp_tools(session)
    
    # LLM с инструментами
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        temperature=0.7,
        client=client
    )
    llm_with_tools = llm.bind_tools(tools)
    
    # Промпт для диагностики
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """Ты - эксперт по диагностике проблем 3D-печати.
        
Используй инструменты для поиска информации в базе знаний.
Дай конкретные рекомендации с параметрами (температура, скорость, retraction).
Если информации недостаточно - задай уточняющие вопросы."""),
        MessagesPlaceholder("messages")
    ])
    
    chat_llm = prompt_template | llm_with_tools
    
    # Узел чата
    def chat_node(state: State) -> State:
        state["messages"] = chat_llm.invoke({"messages": state["messages"]})
        return state
    
    # Построение графа
    graph = StateGraph(State)
    graph.add_node("chat_node", chat_node)
    graph.add_node("tool_node", ToolNode(tools=tools))
    graph.add_edge(START, "chat_node")
    graph.add_conditional_edges("chat_node", tools_condition, {
        "tools": "tool_node",
        "__end__": END
    })
    graph.add_edge("tool_node", "chat_node")
    
    return graph.compile(checkpointer=MemorySaver())

async def main():
    """Главная функция для запуска диагностического агента"""
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            agent = await create_diagnostic_agent(session)
            print("✅ Диагностический агент готов!")
            print("Введите запрос или 'exit' для выхода")
            
            while True:
                try:
                    user_input = input("\n👤 Пользователь: ").strip()
                    
                    if user_input.lower() in {"exit", "quit", "q"}:
                        break
                    
                    if not user_input:
                        continue
                    
                    # Вызов агента
                    response = await agent.ainvoke(
                        {"messages": [HumanMessage(content=user_input)]},
                        config={"configurable": {"thread_id": "diagnostic-session"}}
                    )
                    
                    print(f"\n🤖 Агент: {response['messages'][-1].content}")
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🎯 Преимущества для проекта 3dtoday

### 1. **Чистая архитектура**
- Инструменты KB определены декларативно
- Легко добавлять новые инструменты
- Разделение ответственности

### 2. **Автоматическое использование инструментов**
- LangGraph автоматически решает, когда вызывать инструменты
- Агент сам выбирает нужные инструменты
- Не нужно вручную управлять вызовами

### 3. **Расширяемость**
- Легко добавить новые инструменты (например, анализ изображений)
- Поддержка ресурсов и промптов
- Модульная архитектура

### 4. **Интеграция с существующим кодом**
- Использует существующие сервисы (RAG, VectorDB, KB Curator)
- Не требует переписывания всего кода
- Постепенная миграция

---

## 📋 План интеграции

### Этап 1: Базовый MCP Server (День 1-2)

1. ✅ Создать `kb_mcp_server.py` с базовыми инструментами:
   - `search_kb_articles()`
   - `get_article_by_id()`

2. ✅ Протестировать подключение к MCP серверу

3. ✅ Интегрировать с существующим RAG сервисом

### Этап 2: Расширенные инструменты (День 3-4)

1. ✅ Добавить инструменты KB Curator:
   - `validate_article_relevance()`
   - `generate_qa_from_article()`
   - `add_article_to_kb()`

2. ✅ Добавить ресурсы и промпты

### Этап 3: Diagnostic Client (День 5)

1. ✅ Создать `diagnostic_mcp_client.py`
2. ✅ Интегрировать с LangGraph
3. ✅ Протестировать диагностику

### Этап 4: Интеграция с FastAPI (День 6-7)

1. ✅ Создать FastAPI endpoint, использующий MCP агента
2. ✅ Интегрировать с Streamlit интерфейсом
3. ✅ Тестирование

---

## 🔄 Использование в MVP

### Вместо прямых вызовов сервисов:

**Было:**
```python
# Прямой вызов RAG
rag_service = RAGService()
results = rag_service.search(query, filters=filters)
```

**Стало:**
```python
# Через MCP агента
agent = await create_diagnostic_agent(session)
response = await agent.ainvoke({"messages": [HumanMessage(content=query)]})
# Агент сам вызовет нужные инструменты
```

### Преимущества:

✅ **Автоматическое управление** — агент сам решает, какие инструменты использовать
✅ **Чистый код** — не нужно вручную управлять вызовами
✅ **Расширяемость** — легко добавлять новые инструменты
✅ **Тестируемость** — легко тестировать отдельные инструменты

---

## 📚 Структура файлов

```
backend/app/
├── mcp/
│   ├── kb_mcp_server.py          # MCP сервер с инструментами KB
│   └── diagnostic_mcp_client.py  # Клиент с LangGraph агентом
├── agents/
│   └── kb_curator.py              # Используется MCP сервером
└── services/
    ├── rag.py                     # Используется MCP сервером
    └── vector_db.py               # Используется MCP сервером
```

---

## ✅ Чек-лист реализации

### День 1-2:
- [ ] Создать `kb_mcp_server.py` с базовыми инструментами
- [ ] Протестировать подключение к MCP серверу
- [ ] Интегрировать с RAG сервисом

### День 3-4:
- [ ] Добавить инструменты KB Curator
- [ ] Добавить ресурсы и промпты
- [ ] Протестировать все инструменты

### День 5:
- [ ] Создать `diagnostic_mcp_client.py`
- [ ] Интегрировать с LangGraph
- [ ] Протестировать диагностику

### День 6-7:
- [ ] Интегрировать с FastAPI
- [ ] Интегрировать с Streamlit
- [ ] Финальное тестирование

---

## 🎯 Критерии успеха

✅ **MCP сервер работает** — инструменты загружаются и вызываются
✅ **Агент использует инструменты** — автоматически вызывает нужные инструменты
✅ **Интеграция с существующим кодом** — использует RAG, VectorDB, KB Curator
✅ **Расширяемость** — легко добавлять новые инструменты

---

## 💡 Дополнительные возможности

### Будущие улучшения:

1. **Инструменты для Vision Agent**
   - `analyze_image()` — анализ изображения дефекта
   - `extract_problem_from_image()` — извлечение типа проблемы

2. **Инструменты для управления KB**
   - `delete_article()` — удаление статьи
   - `update_article()` — обновление статьи
   - `get_kb_statistics()` — статистика KB

3. **Ресурсы**
   - `kb://articles/top-10` — топ-10 статей
   - `kb://problems/coverage` — покрытие проблем

4. **Промпты**
   - `qa_generation_prompt()` — генерация Q/A
   - `article_summary_prompt()` — суммаризация статьи

---

## 📖 Дополнительные ресурсы

- [MCP Documentation](https://modelcontextprotocol.io/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- Проект `../mcp/` — пример реализации

**Важно:** Этот подход можно использовать параллельно с существующим кодом, постепенно мигрируя функциональность.



