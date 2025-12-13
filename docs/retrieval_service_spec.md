# Техническое задание
## Микросервис: Retrieval Service (v1)

### 1. Назначение
Выполнять поиск релевантных чанков/секций документов для AI Orchestrator. Источник данных — векторное хранилище с метаданными, заполненное ingestion_service. Сервис обязан фильтровать результаты по tenant и возвращать стабильные идентификаторы/страницы.

### 2. Область ответственности
- Принимать внутренние запросы поиска (`POST /internal/retrieval/search`).
- Выполнять dense поиск по embeddings чанков (и, при необходимости, секций/доков).
- Применять фильтры по tenant и метаданным (doc_ids, product/version/tags).
- Возвращать отсортированный список `hits` с `doc_id/section_id/chunk_id/text/score/page_start/page_end`.
- Давать health-check с проверкой бекенда.

Вне зоны: LLM вызовы, safety, ingestion, reranking кросс-энкодером, query rewriting.

### 3. API
`POST /internal/retrieval/search`
- Request:
  - `query: str` — текст запроса (обязателен).
  - `tenant_id: str` — тенант (обязателен).
  - `max_results?: int` — лимит (дефолт `RETR_MAX_RESULTS`, upper bound 50).
  - `filters?: {product?, version?, tags?: list[str], doc_ids?: list[str], section_ids?: list[str]}`.
  - `trace_id?: str` — для логов/метрик.
- Response (200):
```json
{"hits": [
  {
    "doc_id": "doc_1",
    "section_id": "sec_1",
    "chunk_id": "chunk_1",
    "text": "...",
    "score": 0.92,
    "page_start": 1,
    "page_end": 2
  }
]}
```
- Ошибки: 400 (нет tenant/query или неверные параметры), 502/500 (бекенд недоступен) с кодом `backend_unavailable`.

`GET /health` — `{"status":"ok"}` + проверка доступности бекенда (chroma ping) в поле `details`.

### 4. Данные и бекенд
- Основной бекенд: Chroma (PersistentClient). Коллекции: `ingestion_chunks` (по умолчанию), опционально `ingestion_sections`, `ingestion_docs`.
- Payload/метаданные в коллекциях должны содержать: `tenant_id`, `doc_id`, `section_id`, `chunk_id`, `text`, `page_start`, `page_end`, и доп. поля (product/version/tags).
- Мок-режим: in-memory индекс с фиксированными данными для тестов.

### 5. Поисковая логика
- Этап 1. **Doc-level top-K** (опционально, если есть doc embeddings): dense поиск по doc коллекции → фильтр по tenant/filters → `topk_docs`.
- Этап 2. **Section-level top-M**: среди `topk_docs` dense поиск по секционным summary embeddings (или мета) → `topk_sections` с лимитом per doc (конфигurable) и общим лимитом `max_results` (или отдельный `max_sections`).
- Этап 3. **Chunk-level (точность)**: если доступны chunk embeddings, ищем в chunks только для найденных секций/доков, применяем `topk_per_doc` и общий `max_results`.
- Post-processing:
  - сортировка по score убыванию;
  - дедуп по `chunk_id`;
  - отсев ниже `min_score` (если настроено);
  - усечение до `max_results`.
- Содержимое `text` в ответе может быть: summary секции (если chunk не извлекается) либо сам chunk.text. Полный текст для LLM доступен через MCP по `doc_id` + `page_start/page_end`.
- Если бекенд недоступен — вернуть 502/500 с кодом `backend_unavailable` (не падать 500 без пояснения).
- Мок-режим — возврат стабильных hits из фиксированного списка.

### 6. Конфигурация (ENV, префикс `RETR_`)
- `MOCK_MODE` — включить in-memory backend.
- `VECTOR_BACKEND` — `chroma` (по умолчанию).
- `CHROMA_PATH` или `CHROMA_HOST` — параметры подключения.
- `MAX_RESULTS` — дефолтный лимит.
- `TOPK_PER_DOC` — максимум чанков на документ (0 — без лимита).
- `MIN_SCORE` — отсев по минимальному score (опц.).
- `LOG_LEVEL`.
- Таймауты запросов к Chroma.

### 7. Наблюдаемость и логи
- Логи (structlog): `trace_id`, `tenant_id`, `max_results`, `filters`, `hits_count`, `latency_ms`, `backend`.
- Метрики (минимум план): `retrieval_requests_total`, `retrieval_latency_ms`, `retrieval_hits_total`, `retrieval_errors_total`, `backend_unavailable_total`.

### 8. Безопасность
- `tenant_id` обязателен и используется в фильтрах.
- Ограничение `max_results` верхним порогом (например, 50) для защиты бекенда.
- Нет публичной авторизации (внутренний сервис); защита сетью/mesh.

### 9. Тестирование
- Unit: фильтры, лимиты, сортировка, shape ответа, поведение `max_results`/`topk_per_doc`.
- Integration: Chroma backend (docker) — поиск по фикстурным чанкам, проверка фильтрации по tenant и doc_id.
- E2E: совместимость с Orchestrator через ASGITransport (по аналогии с `tests/test_pipeline_integration.py`).

### 10. Развёртывание
- Dockerfile сервиса, env `RETR_*`.
- Docker-compose: добавить сервис Chroma (если не используется общий), прокинуть volume для `CHROMA_PATH`.
- Healthcheck должен падать при недоступности Chroma в prod-режиме.
