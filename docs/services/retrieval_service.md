# Retrieval Service — Техническое задание (v1)

## Назначение
Сервис выполняет поиск релевантных чанков/секций документов для AI Orchestrator. Должен работать с векторным хранилищем (Chroma/PGVector и т.п.), применять фильтры по тенанту/метаданным и возвращать стабильные идентификаторы и страницы.

## Требования
1. **API**
   - `POST /internal/retrieval/search`
     - Request: `query: str`, `tenant_id: str`, `max_results?: int=5`, `filters?: {product?, version?, tags?, doc_ids?, section_ids?}`, `doc_ids?: list[str]`, `section_ids?: list[str]`.
     - Response: `{"hits": [...], "steps": {"docs": [...], "sections": [...], "chunks": [...]}}` (steps опционально). `score` по убыванию, стабильные ID.
   - `/health` — ok + проверка доступности backend.
2. **Данные и backend**
   - Векторное хранилище: адаптер с интерфейсом `search(query: RetrievalQuery) -> list[RetrievalHit]`. Базовая реализация — Chroma (использует коллекции, наполняемые ingestion_service). Поддержать мок-режим (in-memory список).
   - Фильтрация по `tenant_id` обязательна; поддержать фильтры по `doc_id`, метаданным (product/version/tags) из мета в vector store.
   - Параметры: `max_results` (глобальный лимит), `topk_per_doc` (лимит чанков на документ), `min_score` (опциональный отсев).
3. **Логика поиска**
   - Этап 1: doc-level top-K (если есть doc embeddings) с фильтрами по tenant/метаданным → `topk_docs`.
   - Этап 2: section-level top-M в пределах найденных документов (summary embeddings/мета) → лимит per-doc + глобальный `max_results`/`max_sections`.
   - Этап 3: chunk-level уточнение (chunk embeddings) → `topk_per_doc` и общий `max_results`.
   - Постобработка: сортировка по score убыванию, отсев ниже `min_score`, дедуп по `chunk_id`, обрезка до `max_results`.
   - `text` в hits может быть summary секции или chunk text; полный текст LLM может получить через MCP по `doc_id` и `page_start/page_end`.
4. **Конфигурация (ENV)**
   - `RETR_MOCK_MODE` — использовать in-memory индекс.
   - `RETR_MAX_RESULTS` (дефолт 5), `RETR_TOPK_PER_DOC`, `RETR_MIN_SCORE`.
   - `RETR_VECTOR_BACKEND` (например, `chroma`), `RETR_CHROMA_PATH`/`RETR_CHROMA_HOST`.
   - `RETR_DOC_SERVICE_BASE_URL` — для валидации/фильтров (опционально).
   - `RETR_LOG_LEVEL`, таймауты backend.
5. **Безопасность/тенантность**
   - `tenant_id` обязателен, используется в фильтрах backend.
   - Лимитировать `max_results` сверху (например, 50).
6. **Наблюдаемость**
   - Логи: запрос, tenant, latency, backend, кол-во результатов.
   - Метрики (план): latency p95, hits count, errors; healthcheck должен отражать состояние backend.
7. **Отказоустойчивость**
   - Таймауты/обработка ошибок backend → возвращать 502/500 с кодом `backend_unavailable`.
   - Мок-режим без зависимостей.
8. **Тесты**
   - Unit: фильтры, лимиты, сортировка, shape ответа.
   - Интеграция: с локальной Chroma (docker-compose) — проверка поиска/tenant фильтрации.
   - E2E (опционально): совместно с Orchestrator (ASGITransport, как в `tests/test_pipeline_integration.py`).

## Архитектура (предложение)
- FastAPI (`services/retrieval_service`), адаптер backend в `core/index.py` (интерфейс + Chroma реализация + InMemory).
- Конфиг через `RETR_*`, логирование через structlog.
- Документация: обновить спецификацию `docs/retrieval_service_spec.md` после реализации.
