# Состояние микросервисов (main)

Статусы: `Mock` — готово для локалки/тестов, но требует внешних сервисов для прод; `Baseline` — рабочий функционал без сложных зависимостей; `Playground` — утилитарные возможности без жёстких контрактов.

| Сервис | Статус | Комментарии |
| --- | --- | --- |
| API Gateway | Mock | Edge на FastAPI, инMemory rate limit, mock introspection; проксирует safety/orchestrator/ingestion/doc. Нет реальной авторизации, Document клиент зовёт нестандартный `/internal/documents/list`. |
| Safety Service | Baseline | Input/output guard с блоклистом, PII‑редакцией и prompt‑injection детектором. Без внешних моделей. |
| MCP Tools Proxy | Baseline (mock data) | Инструменты MCP + rate limit, документы в in-memory репозитории. `read_chunk_window` требует заданного Retrieval URL. |
| LLM Service | Mock | Tool-loop над OpenAI‑style runtime и MCP proxy, JSON‑mode флаг. По умолчанию mock runtime/proxy; нет safety. |
| AI Orchestrator | Mock | Retrieval → LLM runtime → MCP инструменты, прогрессивное окно чанков. Output safety не подключён; mock режим возвращает заглушки. |
| Document Service | Baseline | Async SQLAlchemy + SQLite/S3‑клиент. При `mock_mode=false` требует Postgres+S3, иначе падает при старте. Tenant isolation на чтение. |
| Ingestion Service | Mock | Очередь/JobStore in-memory или Redis, обработка файла → чанки/summary/эмбеддинги, запись в Document Service и Chroma (если включено). Worker background, без надёжной очереди. |
| Retrieval Service | Mock/Chroma | Ступенчатый поиск doc/section/chunk в Chroma, фильтры и rerank опционален; есть chunk window endpoint. В mock режиме отдаёт фиксированные hits. |
| ML Observer Service | Playground | SQLite + FastAPI, прокси в ingestion/doc/retrieval/orchestrator при наличии URL, mock retrieval/LLM иначе. UI `/ui`, без авторизации. |

Общее: большинство сервисов стартуют в mock режиме; для прод нужно задать реальные DSN/ключи/URL и включить внешние хранилища и runtime.
