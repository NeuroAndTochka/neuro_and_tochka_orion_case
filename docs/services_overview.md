# Обзор микросервисов Orion

Краткая выжимка по текущему состоянию сервисов в репозитории. Все приложения написаны на FastAPI, по умолчанию работают в `mock_mode` и общаются друг с другом по HTTP.

## API Gateway
- **Зачем.** Единственная публичная точка (`/api/v1/...`). Делает аутентификацию (mock introspection по умолчанию), rate limit и input safety перед проксированием в оркестратор.
- **Эндпоинты.** `/api/v1/health`, `/api/v1/auth/me`, `/api/v1/assistant/query`, `/api/v1/documents/upload`, `/api/v1/documents`, `/api/v1/documents/{doc_id}`.
- **Зависимости.** Safety input check, AI Orchestrator, Ingestion, Document Service; HTTP клиенты лежат в `api_gateway/clients`.
- **Конфиг.** `API_GATEWAY_*` (base URLs, таймауты, rate_limit_per_minute, mock_mode, CORS).

## Safety Service
- **Зачем.** Rule-based проверка входа/выхода: блоклисты, простое PII, prompt injection.
- **Эндпоинты.** `/internal/safety/input-check`, `/internal/safety/output-check`.
- **Конфиг.** `SAFETY_SERVICE_*`: `policy_mode` (strict/balanced/relaxed), `blocklist`, `enable_pii_sanitize`, `default_policy_id`.

## AI Orchestrator
- **Зачем.** Склеивает Retrieval → LLM runtime → MCP инструменты, формирует ответ и источники.
- **Эндпоинты.** `/internal/orchestrator/respond`, `/internal/orchestrator/config` (GET/POST), `/health`.
- **Поведение.** Первый prompt строится только из запроса и summary/метаданных секций (без raw текста) и сообщает LLM про отсутствие полного текста; `text` из Retrieval отбрасывается. Tool-loop использует MCP-инструменты `read_chunk_window`/`read_doc_section`, прогрессивно расширяет окно до радиуса `R` и контролирует `context_token_budget`. `mock_mode` отдаёт заглушки.
- **Конфиг.** `ORCH_*`: URLs зависимостей, `default_model`, `prompt_token_budget`, `context_token_budget`, `max_tool_steps`, `window_radius` (per-side R, total = 2R+1, из `RAG_WINDOW_RADIUS`/`ORCH_WINDOW_RADIUS`), `mock_mode`; легаси `window_initial/step/max` приводятся к `window_radius`.

## LLM Service
- **Зачем.** Принимает `GenerateRequest`, вызывает LLM runtime (OpenAI-style) и MCP proxy в tool-loop, возвращает ответ/usage/trace.
- **Эндпоинты.** `/internal/llm/generate`, `/health`.
- **Конфиг.** `LLM_SERVICE_*`: `llm_runtime_url`, `default_model`, `max_tool_steps`, `enable_json_mode`, `mcp_proxy_url`, `mock_mode`.

## MCP Tools Proxy
- **Зачем.** Исполняет безопасные инструменты для LLM/MCP. Данные документов берёт из in-memory репозитория; умеет ходить в Retrieval за окном чанков.
- **Эндпоинты.** `/internal/mcp/execute`, `/health`.
- **Инструменты.** `read_doc_section`, `read_doc_pages`, `read_doc_metadata`, `doc_local_search`, `read_chunk_window`, `list_available_tools` — единственный источник raw текста для LLM.
- **Конфиг.** `MCP_PROXY_*`: `max_pages_per_call`, `max_text_bytes`, `rate_limit_calls`, `rate_limit_tokens`, `max_window_radius` (per-side R из `RAG_WINDOW_RADIUS`/`MCP_PROXY_MAX_WINDOW_RADIUS`, легаси `MCP_PROXY_MAX_CHUNK_WINDOW` → `floor((N-1)/2)`), `retrieval_window_url`, `mock_mode`.

## Document Service
- **Зачем.** Хранит метаданные документов/секций/тегов, выдаёт download URL, принимает статусы ingestion.
- **Эндпоинты.** `/internal/documents` (GET/POST), `/internal/documents/{doc_id}`, `/internal/documents/{doc_id}/sections/{section_id}`, `/internal/documents/{doc_id}/sections` (POST), `/internal/documents/status`, `/internal/documents/{doc_id}/download-url`, `/health`. Требует `X-Tenant-ID` на чтение.
- **Хранилище.** Async SQLAlchemy + SQLite по умолчанию; Postgres + S3/MinIO при `mock_mode=false`.
- **Конфиг.** `DOC_*`: `db_dsn`, `mock_mode`, `s3_*`, `local_storage_path`, `download_url_expiry_seconds`.

## Ingestion Service
- **Зачем.** Принимает файлы, сохраняет в storage, строит чанки/summary/эмбеддинги, опционально пишет в Document Service и Chroma.
- **Эндпоинты.** `/internal/ingestion/enqueue`, `/internal/ingestion/status`, `/internal/ingestion/jobs/{job_id}`, `/internal/ingestion/summarizer/config` (GET/POST), `/internal/ingestion/chunking/config` (GET/POST), `/internal/ingestion/documents/{doc_id}/tree`, `/health`. Требует `X-Tenant-ID` для пользовательских вызовов.
- **Поведение.** JobStore + очередь (in-memory или Redis), фоновые воркеры, EmbeddingClient и Summarizer с OpenAI-совместимыми API или mock, vector store опционально.
- **Конфиг.** `INGEST_*`: storage/S3, `doc_service_base_url`, `redis_url`, `worker_count`, `embedding_*`, `summary_*`, `chunk_size`, `chunk_overlap`, `chroma_path/host`, `mock_mode`.

## Retrieval Service
- **Зачем.** Dense/metadata поиск по doc/section/chunk индексам (Chroma) или in-memory мок.
- **Эндпоинты.** `/internal/retrieval/search`, `/internal/retrieval/config` (GET/POST), `/internal/retrieval/chunks/window`, `/health`.
- **Поведение.** Ступенчатый поиск (docs → sections → chunks) с фильтрами по tenant/product/tags/doc_ids/section_ids, опциональный rerank через OpenAI-клиент. По умолчанию отдаёт только id/summary/метаданные/score (поле `text` скрыто), chunk-результаты могут быть пустыми; raw текст отдаёт только `/chunks/window`.
- **Конфиг.** `RETR_*`: `mock_mode`, `vector_backend`, `chroma_path/host/collection`, `max_results`, `topk_per_doc`, `min_score`, `doc/section/chunk_top_k`, `min_docs`, `enable_filters`, `rerank_*`, `embedding_*`.

## ML Observer
- **Зачем.** Playground/прокси для ML-команды: загрузки, прогоны retrieval, dry-run LLM/Orchestrator, UI.
- **Эндпоинты.** `/internal/observer/...` (experiments, documents/upload, ingestion proxies, retrieval/orchestrator proxies, config passthrough) и `/ui`.
- **Конфиг.** `OBS_*`: `db_dsn` (SQLite по умолчанию), base URL других сервисов, `mock_mode`.

## Общие заметки
- Почти все сервисы имеют `/health`.
- Большинство конфигов переключаются `mock_mode`; при `mock_mode=false` отдельные сервисы требуют реальные DSN/ключи и выкидывают ошибку инициализации.
- Запуск всех сервисов локально: `docker compose up --build`; тесты: `pytest` из корня или `run_tests.sh` в сервисах.
