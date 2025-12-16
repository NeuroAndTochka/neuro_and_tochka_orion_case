# Документация по API Orion Soft — Visior

Актуальные публичные (`/api/v1/...`) и внутренние (`/internal/...`) контракты. Все сервисы — FastAPI, большинство работает в `mock_mode` по умолчанию.

## 0. Общие правила
- Передача данных — JSON/UTF-8 (кроме multipart загрузки).
- Публичные запросы требуют `Authorization: Bearer ...`; внутренние сервисы полагаются на сетевую изоляцию и заголовок `X-Tenant-ID` при доступе к документам.
- `X-Request-ID` генерируется API Gateway и прокидывается вниз; ответ оркестратора возвращает `trace_id`.

---

# 1. Публичный API (API Gateway)
Базовый префикс: `/api/v1`.

## 1.1 Health
`GET /api/v1/health` → `{"status":"ok"}`.

## 1.2 Аутентификация
`GET /api/v1/auth/me` — профиль пользователя: `user_id`, `username`, `display_name?`, `roles[]`, `tenant_id`.

## 1.3 Ассистент
`POST /api/v1/assistant/query`
```json
{
  "query": "Как настроить LDAP?",
  "language": "ru",
  "context": {"channel": "web", "ui_session_id": "sess", "conversation_id": "conv"}
}
```
Ответ: `answer: str`, `sources: [{doc_id, doc_title?, section_id?, section_title?, page_start?, page_end?}]`, `meta: {latency_ms?, trace_id, safety?}`. При блокировке safety — 400 с detail `{code: "safety_blocked", reason: "..."}`.

## 1.4 Документы
- `POST /api/v1/documents/upload` — multipart `file` + опц. `product/version/tags`; ответ `{"doc_id": "...", "status": "queued"}`.
- `GET /api/v1/documents` — список `DocumentItem` (doc_id, name, status, product?, version?, tags[], created_at?, updated_at?).
- `GET /api/v1/documents/{doc_id}` — `DocumentDetail` (поля списка + pages?, sections?).

---

# 2. Внутренние API

## 2.1 Safety Service (`/internal/safety`)
- `POST /input-check` — поля `user`, `query`, опц. `channel/context/meta`. Ответ `SafetyResponse` со статусом `allowed|transformed|blocked`, risk_tags, `transformed_query?`, `trace_id`.
- `POST /output-check` — `user`, `query`, `answer`, опц. `sources/meta/context`; возвращает `SafetyResponse` с возможной `transformed_answer`.

## 2.2 AI Orchestrator (`/internal/orchestrator`)
- `POST /respond` — ожидает `query`, `user` или пару `user_id/tenant_id`, опц. `trace_id`, `filters`, `doc_ids`, `section_ids`, `max_results`. Возвращает `answer`, `sources`, `tools`, `safety`, `telemetry`.
- `GET/POST /config` — runtime конфиг (model, budgets, tool window, mock_mode).
- `/health` — `{"status":"ok"}`.

## 2.3 Retrieval Service (`/internal/retrieval`)
- `POST /search`
```json
{
  "query": "...",
  "tenant_id": "tenant_1",
  "max_results": 5,
  "filters": {"product": "...", "version": "...", "tags": ["..."], "doc_ids": ["..."], "section_ids": ["..."]},
  "doc_ids": ["..."],
  "section_ids": ["..."],
  "enable_filters": true,
  "rerank_enabled": false,
  "trace_id": "trace-123"
}
```
Ответ: `{"hits": [...], "steps": {"docs": [...], "sections": [...], "chunks": [...]}}` (steps опционален).
- `GET/POST /config` — настраивает `max_results`, topK, rerank, фильтры.
- `POST /chunks/window` — `tenant_id`, `doc_id`, `anchor_chunk_id`, опц. `window_before/after` → `{"chunks":[{chunk_id,page,chunk_index,text}]}`.
- `/health` — проверка Chroma в prod-режиме.

## 2.4 LLM Service (`/internal/llm`)
- `POST /generate` — `system_prompt`, `messages[{role,content}]`, `context_chunks[{doc_id, section_id?, text, page_start?, page_end?}]`, `generation_params` (top_p, penalties, stop?), `trace_id?`.
- Ответ: `answer`, `used_tokens{prompt,completion}`, `tools_called[]`, `meta{model_name, trace_id, tool_steps}`. `/health` отдаёт `ok`.

## 2.5 MCP Tools Proxy (`/internal/mcp`)
- `POST /execute` — `tool_name`, `arguments`, `user{user_id,tenant_id,roles?}`, `trace_id?`.
- Ответ: `{status: "ok"|"error", result?|error?, trace_id}`. Доступные инструменты: `list_available_tools`, `read_doc_section`, `read_doc_pages`, `read_doc_metadata`, `doc_local_search`, `read_chunk_window`.
- `/health` — `ok`.

## 2.6 Document Service (`/internal/documents`)
- `POST /internal/documents` — create/update метаданные (payload включает `doc_id`, `tenant_id`, `name`, `status`, опц. `product/version/tags/storage_uri/pages`).
- `GET /internal/documents` — требует `X-Tenant-ID`; фильтры `status|product|tag|search`, пагинация `limit/offset`. Ответ `{total, items: [...]}`.
- `GET /internal/documents/{doc_id}` и `/sections/{section_id}` — detail/section (заголовок, страницы, chunk_ids, summary).
- `POST /internal/documents/{doc_id}/sections` — батч upsert секций.
- `POST /internal/documents/status` — обновление статуса/ошибки/страниц, позже отдаёт detail.
- `GET /internal/documents/{doc_id}/download-url` — временная ссылка (локальная или S3).
- `/health` — `ok`.

## 2.7 Ingestion Service (`/internal/ingestion`)
- `POST /enqueue` — multipart `file`, опц. `product/version/tags`, заголовок `X-Tenant-ID`. Ответ `job_id`, `doc_id`, `status`, `storage_uri`.
- `POST /status` — `job_id`, `status`, `error?`.
- `GET /jobs/{job_id}` — состояние + логи.
- `GET/POST /summarizer/config` — конфиг summarizer (model, prompt, use_roles).
- `GET/POST /chunking/config` — `chunk_size`, `chunk_overlap`.
- `GET /documents/{doc_id}/tree` — дерево секций + чанки из vector store (если включён).
- `/health` — `ok`.

## 2.8 ML Observer (`/internal/observer`)
- Эксперименты (`POST /experiments`, `GET /experiments/{id}`), загрузка документов, прокси в ingestion/doc/retrieval/orchestrator (`/ingestion/enqueue|status|jobs`, `/retrieval/search|config`, `/orchestrator/respond`), dry-run LLM. Требует `X-Tenant-ID`. UI: `GET /ui`.
