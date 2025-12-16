# AI Orchestrator

## Назначение
Собирает контекст из Retrieval Service и orchestrat'ит tool-loop с LLM runtime и MCP Tools Proxy. Возвращает ответ, источники и телеметрию для API Gateway.

## Эндпоинты (`/internal/orchestrator`)
- `POST /respond` — принимает `query`, `user` или `user_id+tenant_id`, опц. `trace_id`, `filters`, `doc_ids`, `section_ids`, `max_results`. Ответ: `answer`, `sources`, `tools`, `safety`, `telemetry`.
- `GET/POST /config` — runtime настройки (model, budgets, tool window, mock_mode).
- `/health` — базовый healthcheck.

## Поток обработки
1. Проверяет наличие user context; без него отдаёт 400.
2. Если user не передан, встает дефолтный user/tenant из конфигурации (`default_user_id/default_tenant_id`). Запрашивает `/internal/retrieval/search` (капитирует `max_results` до `Settings.max_results`) и выкидывает поле `text` из hits.
3. Строит summary-контекст (без полного текста) и первый prompt: только query + список секций (id/summary/pages/score) с инструкцией, что полного текста нет и его нужно вытягивать MCP инструментами.
4. Запускает tool-loop (ограничение `max_tool_steps`). Предпочитает `read_chunk_window`; если anchor chunk отсутствует, принудительно использует `read_doc_section`. Raw текст попадает к модели только через TOOL_RESULT MCP.
5. Суммирует использованные токены (prompt + текст из tool-результатов); превышение `context_token_budget` даёт ошибку.

## Конфигурация (`ORCH_*`)
`retrieval_url`, `mcp_proxy_url`, `llm_runtime_url`, `default_model`, `prompt_token_budget`, `context_token_budget`, `max_tool_steps`, `window_initial/step/max`, `mock_mode`.

## Особенности
- `mock_mode=true` (по умолчанию) — retrieval/LLM/MCP клиенты возвращают заглушки; tool-loop завершается за 1–2 шага.
- Output safety пока не вызывается; безопасность только на входе через Gateway.
- progressive window увеличивает количество чанков на секцию, если модель повторно запрашивает данные.
