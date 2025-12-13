# Состояние микросервисов (main)

Статусы: `Prod ready` — можно разворачивать (mock-флаги для локалки остаются); `Skeleton` — базовый API без продовой интеграции; `Needs work` — известные пробелы.

| Сервис | Статус | Комментарии |
| --- | --- | --- |
| API Gateway | Skeleton/Mock | FastAPI edge, клиенты к safety/orchestrator/document/ingestion. Mock auth/rate-limit, нет продовой авторизации. |
| Safety Service | Skeleton | Input/output guard с правилами PII/keywords, без внешних моделей, API стабильный. |
| MCP Tools Proxy | Prod ready (mock data) | MCP-инструменты с rate-limit. Репозиторий документов in-memory, набор инструментов базовый. |
| LLM Service | Skeleton/Mock | Оркестратор LLM + MCP, mock runtime/proxy по умолчанию; JSON-mode и лимиты шагов, нет реального runtime. |
| AI Orchestrator | Skeleton/Mock | Контекст из Retrieval → LLM → Safety output, минимальный context builder, mock retrieval/llm. |
| Document Service | Prod ready (SQLite/MinIO-ready) | Async SQLAlchemy, CRUD документов/секций, S3/local storage, tenant isolation. В проде требует Postgres+S3. |
| Ingestion Service | Skeleton + pipeline | Upload → embeddings + LLM summary → секции в Document Service, опциональный Chroma vector store. JobStore in-memory/Redis, фоновые задачи вместо очереди, без ретраев S3. |
| Retrieval Service | Skeleton/Mock | In-memory поиск, контракт `/internal/retrieval/search`, готов к замене на векторную БД. |
| ML Observer Service | Skeleton/Mock | FastAPI+SQLite, эксперименты/раны/документы, mock retrieval/LLM, прокси в ingestion/doc при заданных URL, UI `/ui`, без auth. |

Общее: код покрыт unit/integration тестами; для прод-окружения нужно отключать mock_mode и подключать реальные DSN/URL/хранилища (ingestion, retrieval, LLM runtime, auth в gateway).***
