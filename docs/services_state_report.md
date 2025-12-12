# Состояние микросервисов (feature/ml-observer-service)

Статусы: `Prod ready` — можно разворачивать (с mock-флагами для локалки); `Skeleton` — базовый API, без продовой интеграции; `Needs work` — известные пробелы.

| Сервис | Статус | Комментарии |
| --- | --- | --- |
| API Gateway | Skeleton/Mock | FastAPI, клиенты к safety/orchestrator/document/ingestion. Работает в mock_mode, нет реальной авторизации. Тесты `services/api_gateway/tests` зелёные. |
| Safety Service | Skeleton | Input/output guard с простыми правилами. Без внешних моделей, но API стабильный. Тесты проходят. |
| MCP Tools Proxy | Prod ready (mock tools) | Выполняет MCP-инструменты, есть rate-limit. Использует mock-инструменты (`list_tools`, `local_search`). Тесты зелёные. |
| LLM Service | Skeleton/Mock | Оркестратор вызова LLM + MCP. Работает в mock_mode, без реального runtime. Тесты unit/integration проходят. |
| AI Orchestrator | Skeleton/Mock | Собирает контекст от retrieval → LLM → safety. Работает в mock_mode, контракт выдержан. Тест `services/ai_orchestrator/tests` зелёный. |
| Document Service | Prod ready (SQLite/MinIO-ready) | Async SQLAlchemy, CRUD документов/секций, S3/local storage, tenant isolation. Есть интеграционный тест с Postgres (Testcontainers) и локальные тесты. |
| Ingestion Service | Skeleton (fixed deps) | Очередь in-memory, API `/enqueue` с file upload. Добавлена зависимость `python-multipart` для docker-compose. Нет реальной очереди/S3. |
| Retrieval Service | Skeleton/Mock | In-memory поиск, контракт `/internal/retrieval/search` соблюдён. Готов к замене на векторную БД. |
| ML Observer Service | Skeleton/Mock (новый) | FastAPI + SQLite, хранение экспериментов/ранов/документов. Mock endpoints для retrieval/LLM. Встроенный веб-UI `/ui` для health и ручных запусков. Тест `services/ml_observer/tests/test_observer.py` зелёный. |

Общее: все 29 автотестов из корня проходят (включая Postgres Testcontainers, при наличии Docker). Для выхода в прод потребуется: отключить mock_mode, подключить реальные DSN/базовые URL, заменить in-memory/mock реализации (ingestion, retrieval, LLM runtime).***
