# Technical Specification — MCP Tools Proxy

## 1. Purpose
Provide a safe set of MCP tools for LLM runtime. Works as a FastAPI service with a single endpoint that executes registered tools, applies simple rate limits and optional tenant checks using local metadata. Document content is stored in an in-memory repository by default.

## 2. API
- `POST /internal/mcp/execute`
  - Request: `{"tool_name": "read_doc_section", "arguments": {...}, "user": {"user_id", "tenant_id", "roles?"}, "trace_id?": "..."}`
  - Response: `{"status": "ok"|"error", "result"?: {...}, "error"?: {"code","message"}, "trace_id": "..."}`
- `GET /health` → `{status: "ok"}`.

## 3. Tools (current set)
- `read_doc_section` — doc_id + section_id, returns trimmed text, section_id, doc_id, token estimate.
- `read_doc_pages` — doc_id + page_start/page_end (<= `max_pages_per_call`), возвращает текст страниц.
- `read_doc_metadata` — doc_id → метаданные (title, pages, sections, tags, tenant).
- `doc_local_search` — doc_id + query + `max_results<=5`, возвращает сниппеты.
- `read_chunk_window` — doc_id + anchor_chunk_id (+ window_before/window_after>=0, либо `radius`); проверяет радиус окна (per-side) и ходит в Retrieval Service `/internal/retrieval/chunks/window`, режет текст до `max_text_bytes`.
- `list_available_tools` — список зарегистрированных инструментов.

## 4. Behaviour
- Rate limiting: `rate_limit_calls` + `rate_limit_tokens` на ключ `tenant_id:doc_id` (приблизительная оценка токенов — длина текста/4).
- Tenant isolation: проверяется по локальному `DocumentRepository` (seed `doc_1`/`tenant_1`). Для `read_chunk_window` дополнительно передаётся `tenant_id` в Retrieval Service.
- При отсутствии настроенного Retrieval URL `read_chunk_window` вернёт 503.
- Все тексты обрезаются по `max_text_bytes`; окно чанков ограничено per-side `max_window_radius` (total = 2R+1, по умолчанию `RAG_WINDOW_RADIUS` или `MCP_PROXY_MAX_WINDOW_RADIUS`, легаси `MCP_PROXY_MAX_CHUNK_WINDOW` → `floor((N-1)/2)`).

## 5. Configuration (`MCP_PROXY_*`)
`app_name`, `host/port/log_level`, `max_pages_per_call`, `max_text_bytes`, `rate_limit_calls`, `rate_limit_tokens`, `mock_mode`, `retrieval_window_url`, `retrieval_timeout`, `max_window_radius` (`RAG_WINDOW_RADIUS`/`MCP_PROXY_MAX_WINDOW_RADIUS`, легаси `MCP_PROXY_MAX_CHUNK_WINDOW`), `blocklist_keywords`.

## 6. Testing
Юнит-тесты в `services/mcp_tools_proxy/tests` покрывают инструменты, rate limit и интеграцию с Retrieval Service (ASGITransport для chunk window).
