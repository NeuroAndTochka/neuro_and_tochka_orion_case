# LLM Service

## Назначение
Обёртка над OpenAI-совместимым runtime с поддержкой MCP tool-calls. Принимает `GenerateRequest` от AI Orchestrator и возвращает финальный ответ, usage и трейс инструментов.

## Эндпоинты (`/internal/llm`)
- `POST /generate` — поля: `system_prompt`, `messages[{role,content}]`, `context_chunks[{doc_id, section_id?, text, page_start?, page_end?}]`, `generation_params` (top_p, penalties, stop), `trace_id?`. Ответ: `answer`, `used_tokens{prompt,completion}`, `tools_called[]`, `meta{model_name, trace_id, tool_steps}`.
- `/health` — `{"status":"ok"}`.

## Поведение
- `mock_mode=true` (дефолт) имитирует tool-call или финальный ответ без реального runtime.
- При tool-call вызывает MCP proxy (`MCPClient`) и добавляет `TOOL_RESULT` в историю сообщений.
- Ограничение по количеству шагов — `max_tool_steps`; превышение → 400 с `LLM_LIMIT_EXCEEDED`.
- Может включать JSON mode (`enable_json_mode`) при построении payload для runtime.

## Конфигурация (`LLM_SERVICE_*`)
`llm_runtime_url`, `default_model`, `max_tool_steps`, `enable_json_mode`, `mcp_proxy_url`, `mock_mode`, `host/port/log_level`.
