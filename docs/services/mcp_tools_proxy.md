# MCP Tools Proxy

## Назначение
Промежуточный слой между LLM runtime и внутренними данными. Предоставляет набор ограниченных инструментов, применяет rate limit и проверку tenant на основе метаданных документа.

## Эндпоинт
- `POST /internal/mcp/execute` — `tool_name`, `arguments`, `user{user_id,tenant_id,roles?}`, `trace_id?`. Ответ `{status: ok|error, result?|error?, trace_id}`.
- `/health` — `{"status":"ok"}`.

## Доступные инструменты
- `read_doc_section` — doc_id + section_id, возвращает текст секции (обрезает по `max_text_bytes`).
- `read_doc_pages` — doc_id + page_start/page_end (лимит `max_pages_per_call`).
- `read_doc_metadata` — doc_id → метаданные/секции.
- `doc_local_search` — doc_id + query + max_results≤5, возвращает сниппеты.
- `read_chunk_window` — doc_id + anchor_chunk_id (+ окна), ходит в Retrieval `/chunks/window`, режет текст до `max_text_bytes`.
- `list_available_tools` — перечисление всех инструментов.

## Конфигурация (`MCP_PROXY_*`)
`max_pages_per_call`, `max_text_bytes`, `rate_limit_calls`, `rate_limit_tokens`, `max_chunk_window`, `retrieval_window_url`, `retrieval_timeout`, `blocklist_keywords`, `mock_mode`.

## Источники данных
Документы лежат в in-memory `DocumentRepository` (засеян `doc_1`/`tenant_1`). Tenant проверяется локально; при `mock_mode` разрешены заглушки. Для `read_chunk_window` требуется настроенный Retrieval URL, иначе вернётся `503`.
