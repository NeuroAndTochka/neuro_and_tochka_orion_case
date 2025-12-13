# LLM Service — progress

## Что уже реализовано
- Эндпоинт `/internal/llm/generate` и `/health` на FastAPI (`main.py`, `routers/llm.py`), схемы запросов/ответов в `schemas.py`.
- Основной поток в `core/orchestrator.LLMOrchestrator`: сборка промпта (RAG), вызов LLM runtime, цикл tool-call → MCP proxy, формирование `GenerateResponse` с `answer/used_tokens/tools_called/meta`.
- Клиенты `LLMRuntimeClient` и `MCPClient` с `mock_mode` (статические ответы, имитация tool-call).
- Построение RAG-промпта с включением контекста в `core/prompt.py`.
- Тесты: unit (mock сценарии, tool-loop) и интеграция с реальным MCP proxy и ASGI runtime (`services/llm_service/tests`).

## Как это реализовано
- Конфиг через `LLM_SERVICE_*` (`config.py`): URL runtime/MCP, модель по умолчанию, лимиты шагов/tools (`max_tool_steps`), бюджет completion токенов, принудительный `json_mode`, `mock_mode`.
- В `generate`: собирает сообщения `build_rag_prompt`, хранит usage (`prompt/completion` суммируются из usage runtime), итерирует до `max_tool_steps+1`. При `tool_call` — вызывает MCP (user_claim захардкожен `llm/tenant`), добавляет в диалог сообщение `TOOL_RESULT:...`, накапливает `ToolCallTrace`. При финальном `message` возвращает ответ с `meta` (`model_name` из конфига, `trace_id`, `tool_steps`).
- Payload в runtime включает `response_format={"type": "json_object"}` если включён `enable_json_mode`, и передаёт generation_params (max_tokens/temperature и т.д.), использует `max_completion_tokens` как дефолт.
- `LLMRuntimeClient` умеет маппить OpenAI-style `choices[0].message`/`tool_calls` в `LLMRuntimeResult`; mock ответ может инициировать tool-call по ключу `TOOL_CALL`.
- Интеграционный тест создаёт ASGI runtime, MCP proxy и проходит один tool-step, проверяя финальный ответ/трассировку.

## Что осталось сделать / отклонения от ТЗ
- Нет учёта токен-бюджета промпта (`max_prompt_tokens`) и общего лимита; контекст не триммится/не оценивается по токенам (только прямое включение текста).
- Нет контроля времени/ретраев/таймаутов к runtime/MCP, отсутствуют circuit breaker и повторные попытки, описанные в ТЗ.
- MCP вызовы не используют реальный user/tenant из запроса (захардкожен `{"user_id": "llm", "tenant_id": "tenant"}`); нет валидации/нормализации аргументов tool-call.
- `enable_json_mode` принудительно включает JSON даже при отсутствии инструментов/режимов; `mode` из запроса никак не влияет на поведение/промпт.
- Наблюдаемость: в `meta` нет latency, model_name берётся из конфига, нет метрик (`llm_requests_total`, `llm_latency_ms`, токены/ошибки) и структурированных логов.
- Ошибки MCP/tool-loop: нет стратегии прерывания по числу ошибок, нет обработчиков слишком больших ответов/лимитов; `tool_result` подаётся обратно строкой `TOOL_RESULT:...`, без строгой схемы.
