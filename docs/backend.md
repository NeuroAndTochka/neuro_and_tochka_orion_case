# Документация по backend-архитектуре

Обновлённая картина фактической реализации сервисов в репозитории.

## 1. Цели и текущие ограничения
- RAG-пайплайн с изоляцией tenant и простым safety-контуром.
- Многоступенчатый retrieval (doc → section → chunk) с опциональным rerank.
- Интеграция MCP-инструментов для чтения исходных текстов.
- Автоматизированный ingestion (парсинг, chunking, summary, embeddings) в mock/локальном режиме.
- Большинство сервисов работают в `mock_mode` по умолчанию и требуют внешних URL/DSN только в прод-режиме.

## 2. Высокоуровневая схема
```
Client → API Gateway → Safety (input) → AI Orchestrator
               ↘ documents/upload → Ingestion → Document Service → Retrieval (Chroma)
AI Orchestrator → LLM runtime (OpenAI-style) ↔ MCP Tools Proxy → Retrieval chunk window/локальные документы
```

## 3. Роли сервисов (фактические)
- **API Gateway** — публичные `/api/v1` эндпоинты, mock introspection, rate limit, вызов safety input и оркестратора, прокси загрузок в ingestion.
- **Safety Service** — два rule-based эндпоинта (input/output), блоклист, простая PII-редакция.
- **AI Orchestrator** — вызывается только `/internal/orchestrator/respond`; берёт hits из Retrieval, собирает summary-контекст, запускает tool-loop (read_chunk_window/read_doc_section) через MCP и возвращает ответ/telemetry.
- **LLM Service** — принимает `GenerateRequest`, проксирует в LLM runtime и MCP proxy в цикле tool-calls; mock runtime по умолчанию.
- **MCP Tools Proxy** — in-memory репозиторий документов + инструменты чтения/поиска; `read_chunk_window` ходит в Retrieval; встроенный rate limit.
- **Document Service** — async SQLAlchemy (SQLite по умолчанию), CRUD по документам/секциям/тегам, генерация download URL (локальный путь или S3/MinIO). Требует `X-Tenant-ID` для чтения.
- **Ingestion Service** — принимает файл, сохраняет в storage, строит чанки/эмбеддинги/summary, обновляет Document Service, опционально пишет в Chroma. Очередь/JobStore in-memory или Redis, фоновые воркеры.
- **Retrieval Service** — ступенчатый поиск в Chroma (doc/section/chunk), фильтры по tenant/product/tags/doc_ids, reranker опционален. Имеет `/internal/retrieval/chunks/window`.
- **ML Observer** — playground/proxy: создаёт эксперименты/документы в SQLite, проксирует вызовы ingestion/doc/retrieval/orchestrator при наличии URL; UI на `/ui`.

## 4. Пользовательский запрос (как есть)
1. UI → API Gateway (`/api/v1/assistant/query`): auth (mock), rate limit, input safety.
2. Gateway → Orchestrator: прокидывается `trace_id`, user, safety результат.
3. Orchestrator → Retrieval (`/internal/retrieval/search`) → формирует summary-контекст.
4. Orchestrator → LLM runtime (через LLM Service mock/runtime). LLM может вызывать MCP Tools Proxy (read_chunk_window/read_doc_section).
5. Orchestrator возвращает ответ + sources + telemetry (safety output пока не вызывается).

## 5. Ingestion поток
1. `/api/v1/documents/upload` → Ingestion `/internal/ingestion/enqueue` (требует `X-Tenant-ID`).
2. Сервис сохраняет файл в storage (S3 или локальная папка), создаёт job и запускает `process_file`.
3. Парсинг → секции/чанки → эмбеддинги/summary (OpenAI-style или mock) → upsert в Document Service → upsert в Chroma при включённом vector store.
4. JobStore фиксирует статус; есть ручки `/internal/ingestion/status` и `/internal/ingestion/jobs/{job_id}`.

## 6. Безопасность и изоляция
- `tenant_id` прокидывается от Gateway; Document/Ingress/Observer требуют `X-Tenant-ID` для чтения.
- Safety input/output — отдельный сервис, вызывается только на входе через Gateway (output safety пока не интегрирован в оркестратор).
- MCP инструменты проверяют tenant по локальной метаинформации и ограничивают окно chunk'ов/объём текста.

## 7. Наблюдаемость и тесты
- Все сервисы имеют `/health`; логирование через structlog.
- CI: `pre-commit` + `pytest` (юнит + интеграционные тесты в сервисах, e2e — `tests/test_pipeline_integration.py`).
- Локальный запуск: `docker compose up --build`; для разработки — `pip install -e services/<name>[dev]`.

## 8. Что ещё предстоит
- Подключить реальную авторизацию в Gateway, output safety в оркестраторе.
- Вынести очередь ingestion в надёжный брокер, добавить ретраи сетевых вызовов.
- Добавить экспорт метрик/трейсов и строгие контракты между Gateway ↔ Document Service.
