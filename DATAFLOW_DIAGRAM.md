# Блок-схема датафлоу проекта 3dtoday

## 📊 Основной поток данных (диагностика)

```mermaid
flowchart TD
    Start([Пользователь]) --> Input{Тип ввода}
    
    Input -->|Текст| TextInput[Текстовый запрос]
    Input -->|Изображение| ImageInput[Изображение дефекта]
    Input -->|Текст + Изображение| BothInput[Комбинированный ввод]
    
    TextInput --> Orchestrator[Orchestrator Agent]
    ImageInput --> VisionAgent[Vision Agent]
    BothInput --> VisionAgent
    
    VisionAgent -->|llava Ollama| VisionAnalysis[Анализ изображения]
    VisionAnalysis -->|Fallback| GeminiAPI[Gemini через ProxyAPI]
    GeminiAPI --> VisionResult[Результат анализа:<br/>problem_type, symptoms]
    VisionAnalysis --> VisionResult
    
    VisionResult --> Orchestrator
    BothInput --> Orchestrator
    
    Orchestrator --> SessionContext[SessionContext<br/>- История диалога<br/>- Метаданные<br/>- Состояние]
    
    Orchestrator --> DiagnosticAgent[Diagnostic Agent]
    DiagnosticAgent -->|Использует SessionContext| RAGQuery[Формирование RAG запроса]
    
    RAGQuery --> RetrievalAgent[Retrieval Agent]
    RetrievalAgent --> VectorDB[(Qdrant<br/>Vector DB)]
    
    VectorDB -->|Гибридный поиск| SearchResults[Релевантные статьи<br/>+ метаданные]
    
    SearchResults --> LLM[LLM<br/>Ollama/ProxyAPI]
    SessionContext --> LLM
    
    LLM --> Answer[Сформированный ответ<br/>+ рекомендации]
    
    Answer --> UserResponse([Ответ пользователю])
    
    style Start fill:#e1f5ff
    style UserResponse fill:#e1f5ff
    style VectorDB fill:#fff4e1
    style LLM fill:#e8f5e9
    style SessionContext fill:#f3e5f5
```

## 🔄 Поток данных для добавления статей в KB

```mermaid
flowchart TD
    Start([Новая статья<br/>из парсера/вручную]) --> Parser[Парсер<br/>3dtoday.ru]
    
    Parser --> RawArticle[Сырая статья:<br/>- HTML контент<br/>- Метаданные]
    
    RawArticle --> CuratorAgent[KB Curator Agent]
    
    CuratorAgent --> ContentValidator[Content Validator<br/>Проверка релевантности]
    
    ContentValidator -->|relevance_score < 0.7| Reject1[❌ Отклонено]
    ContentValidator -->|relevance_score >= 0.7| MetadataExtractor[Metadata Extractor<br/>Извлечение метаданных]
    
    MetadataExtractor -->|Нет problem_type| Reject2[❌ Отклонено]
    MetadataExtractor -->|Есть метаданные| QAGenerator[QA Generator<br/>Генерация Q/A пар]
    
    QAGenerator -->|3-5 Q/A пар| KBFormatter[KB Formatter<br/>Форматирование]
    
    KBFormatter --> ArticleData[Статья:<br/>- article_id<br/>- content<br/>- metadata]
    KBFormatter --> QAData[Q/A пары:<br/>- question<br/>- answer<br/>- metadata]
    
    ArticleData --> EmbeddingService[Embedding Service<br/>Генерация эмбеддингов]
    QAData --> EmbeddingService
    
    EmbeddingService --> VectorDB[(Qdrant<br/>Индексация)]
    
    VectorDB --> Success[✅ Статья в KB]
    
    style Start fill:#e1f5ff
    style Success fill:#e8f5e9
    style Reject1 fill:#ffebee
    style Reject2 fill:#ffebee
    style VectorDB fill:#fff4e1
```

## 🔍 Поток данных RAG поиска

```mermaid
flowchart TD
    UserQuery([Запрос пользователя]) --> QueryProcessing[Обработка запроса]
    
    QueryProcessing --> ContextExtraction[Извлечение контекста<br/>из SessionContext]
    
    ContextExtraction --> Filters[Фильтры:<br/>- problem_type<br/>- printer_model<br/>- material]
    
    UserQuery --> EmbeddingGen[Генерация эмбеддинга<br/>запроса]
    
    EmbeddingGen --> VectorSearch[Векторный поиск<br/>в Qdrant]
    Filters --> VectorSearch
    
    VectorSearch --> HybridSearch[Гибридный поиск:<br/>Векторный + Метаданные]
    
    HybridSearch --> TopK[Top-K результатов<br/>k=5]
    
    TopK --> RelevanceFilter[Фильтрация по<br/>relevance_score]
    
    RelevanceFilter --> Articles[Релевантные статьи]
    
    Articles --> ContextFormation[Формирование контекста<br/>для LLM]
    
    ContextFormation --> LLMPrompt[Промпт для LLM:<br/>- Запрос<br/>- Контекст<br/>- Инструкции]
    
    LLMPrompt --> LLM[LLM генерация<br/>Ollama/ProxyAPI]
    
    LLM --> Answer[Ответ с решениями<br/>+ параметрами]
    
    Answer --> UserResponse([Ответ пользователю])
    
    style UserQuery fill:#e1f5ff
    style UserResponse fill:#e1f5ff
    style VectorSearch fill:#fff4e1
    style LLM fill:#e8f5e9
```

## 🤖 Архитектура агентов и их взаимодействие

```mermaid
flowchart LR
    subgraph "Пользовательский запрос"
        User([Пользователь])
        Text[Текст]
        Image[Изображение]
    end
    
    subgraph "Orchestrator Agent"
        Orchestrator[Координатор]
        SessionCtx[SessionContext]
    end
    
    subgraph "Vision Agent"
        Vision[Анализ изображений]
        LLava[llava Ollama]
        Gemini[Gemini ProxyAPI]
    end
    
    subgraph "Diagnostic Agent"
        Diagnostic[Диагностика]
        Questions[Уточняющие вопросы]
    end
    
    subgraph "Retrieval Agent"
        Retrieval[Поиск в KB]
        RAG[RAG Pipeline]
    end
    
    subgraph "KB"
        VectorDB[(Qdrant)]
        Articles[Статьи]
        QA[Q/A пары]
    end
    
    User --> Text
    User --> Image
    
    Text --> Orchestrator
    Image --> Vision
    
    Vision --> LLava
    LLava -->|Fallback| Gemini
    Gemini --> Vision
    Vision --> SessionCtx
    
    Orchestrator --> SessionCtx
    Orchestrator --> Diagnostic
    Orchestrator --> Retrieval
    
    Diagnostic --> SessionCtx
    Diagnostic --> Questions
    Questions --> User
    
    Retrieval --> RAG
    RAG --> VectorDB
    VectorDB --> Articles
    VectorDB --> QA
    
    Articles --> Diagnostic
    QA --> Diagnostic
    
    Diagnostic --> User
    
    style User fill:#e1f5ff
    style SessionCtx fill:#f3e5f5
    style VectorDB fill:#fff4e1
```

## 📥 Поток данных MCP Agent (через MCP протокол)

```mermaid
flowchart TD
    UserRequest([Запрос пользователя]) --> MCPClient[MCP Client<br/>LangGraph Agent]
    
    MCPClient --> MCPSession[MCP Session<br/>stdio transport]
    
    MCPSession --> MCPServer[MCP Server<br/>kb_mcp_server.py]
    
    MCPServer --> Tools{Выбор инструмента}
    
    Tools -->|search_kb_articles| SearchTool[search_kb_articles]
    Tools -->|get_article_by_id| GetTool[get_article_by_id]
    Tools -->|validate_article| ValidateTool[validate_article_relevance]
    Tools -->|generate_qa| QATool[generate_qa_from_article]
    Tools -->|add_article| AddTool[add_article_to_kb]
    
    SearchTool --> RAGService[RAG Service]
    GetTool --> VectorDBService[Vector DB Service]
    ValidateTool --> CuratorService[KB Curator Service]
    QATool --> CuratorService
    AddTool --> CuratorService
    
    RAGService --> VectorDB[(Qdrant)]
    VectorDBService --> VectorDB
    CuratorService --> VectorDB
    
    VectorDB --> Results[Результаты]
    
    Results --> MCPServer
    MCPServer --> MCPSession
    MCPSession --> MCPClient
    MCPClient --> LLM[LLM синтез ответа]
    
    LLM --> UserResponse([Ответ пользователю])
    
    style UserRequest fill:#e1f5ff
    style UserResponse fill:#e1f5ff
    style MCPServer fill:#e8f5e9
    style VectorDB fill:#fff4e1
```

## 🔄 Полный цикл: от запроса до ответа

```mermaid
sequenceDiagram
    participant User as Пользователь
    participant UI as Streamlit UI
    participant API as FastAPI
    participant Orch as Orchestrator
    participant Vision as Vision Agent
    participant Diag as Diagnostic Agent
    participant Retr as Retrieval Agent
    participant KB as Qdrant KB
    participant LLM as LLM
    
    User->>UI: Запрос + фото
    UI->>API: POST /diagnose
    
    API->>Orch: Обработка запроса
    
    alt Есть изображение
        Orch->>Vision: Анализ изображения
        Vision->>LLM: llava анализ
        LLM-->>Vision: Описание дефекта
        Vision-->>Orch: problem_type, symptoms
    end
    
    Orch->>Diag: Диагностика
    Diag->>Orch: Нужен поиск в KB?
    
    alt Нужен поиск
        Orch->>Retr: Поиск в KB
        Retr->>KB: Векторный поиск + фильтры
        KB-->>Retr: Релевантные статьи
        Retr-->>Orch: Контекст для LLM
    end
    
    Orch->>LLM: Генерация ответа
    LLM-->>Orch: Ответ с решениями
    
    alt Нужны уточнения
        Orch->>Diag: Формирование вопросов
        Diag-->>Orch: Уточняющие вопросы
        Orch-->>API: Вопросы пользователю
        API-->>UI: Уточняющие вопросы
        UI-->>User: Вопросы
        User->>UI: Ответ
        UI->>API: Ответ
        API->>Orch: Продолжение диалога
    else Ответ готов
        Orch-->>API: Финальный ответ
        API-->>UI: Ответ с решениями
        UI-->>User: Ответ
    end
```

## 📊 Структура данных в SessionContext

```mermaid
classDiagram
    class SessionContext {
        +str session_id
        +str user_id
        +List messages
        +str diagnostic_state
        +str current_problem_type
        +Dict collected_info
        +Dict vision_result
        +List retrieved_articles
        +str printer_model
        +str material
        +str print_stage
        +datetime created_at
        +datetime updated_at
        +add_message()
        +get_filters()
    }
    
    class VisionResult {
        +str problem_type
        +List symptoms
        +str description
        +float confidence
    }
    
    class Article {
        +str article_id
        +str title
        +str content
        +str problem_type
        +List printer_models
        +List materials
        +List solutions
        +float relevance_score
    }
    
    SessionContext --> VisionResult
    SessionContext --> Article
```

## 🎯 Ключевые точки данных

### Входные данные:
1. **Текстовый запрос пользователя** — описание проблемы
2. **Изображение дефекта** — фото проблемы 3D-печати
3. **Метаданные контекста** — принтер, материал, этап печати

### Промежуточные данные:
1. **SessionContext** — единый контекст сессии
2. **Vision Result** — результат анализа изображения
3. **RAG Query** — запрос для поиска в KB
4. **Search Results** — результаты поиска из Qdrant

### Выходные данные:
1. **Ответ пользователю** — диагностика + решения
2. **Уточняющие вопросы** — если информации недостаточно
3. **Рекомендации** — конкретные параметры и настройки

---

## 📝 Примечания

- **SessionContext** — центральный элемент, хранит весь контекст диалога
- **Гибридный поиск** — комбинация векторного поиска и фильтрации по метаданным
- **MCP протокол** — позволяет агентам автоматически использовать инструменты KB
- **Fallback механизмы** — Ollama → Gemini, llava → Gemini для анализа изображений



