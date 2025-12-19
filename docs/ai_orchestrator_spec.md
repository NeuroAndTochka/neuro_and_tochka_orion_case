# Техническая спецификация — AI Orchestrator

## 1. Назначение
Оркестратор управляет RAG+MCP цепочкой: получает запрос от API Gateway, собирает контекст у Retrieval Service, готовит prompt для LLM runtime и вызывает MCP Tools Proxy в tool-loop, возвращая ответ, источники и телеметрию.

## 2. API
### `POST /internal/orchestrator/respond`
Payload:
- `query: str` (обязателен)
- `user: {user_id, tenant_id, roles?}` **или** `user_id`+`tenant_id`
- опц. `channel`, `locale`, `trace_id`, `filters`, `doc_ids`, `section_ids`, `max_results`

Ответ:
```json
{
  "answer": "...",
  "sources": [{"doc_id": "doc_1", "section_id": "sec_intro", "page_start": 1, "page_end": 2, "score": 0.9}],
  "tools": [{"name": "read_chunk_window", "arguments": {...}, "result_summary": "..."}],
  "safety": {"input": "allowed", "output": "allowed"},
  "telemetry": {"trace_id": "trace-123", "retrieval_latency_ms": 120, "llm_latency_ms": null, "tool_steps": 1}
}
```
Ошибки: 400 при отсутствии user context или превышении лимитов tool-loop/контекста; 502 при ошибках downstream.

### `GET/POST /internal/orchestrator/config`
Возвращает/принимает: `default_model`, `prompt_token_budget`, `context_token_budget`, `max_tool_steps`, `window_radius` (R, общее окно = 2R+1, поступает из `RAG_WINDOW_RADIUS`/`ORCH_WINDOW_RADIUS`, легаси `window_max` → R), `mock_mode`.

### `/health`
`{"status":"ok"}`.

## 3. Поведение
1. Определяет пользователя (использует `user` или пару `user_id/tenant_id`), генерирует trace_id при необходимости.
2. Делает `RetrievalClient.search` с капом `max_results<=50`, добавляет флаги `enable_filters` из конфигурации; поле `text` в hits отбрасывается.
3. В `build_context` обрезает summary до `prompt_token_budget*4` символов и строит первый prompt: только query + список секций (doc_id/section_id/summary/score/pages), без raw текста; системные сообщения явно говорят, что полного текста нет и нужны MCP-инструменты.
4. Tool-loop: LLM runtime может вернуть `tool_call`; оркестратор выбирает `read_chunk_window` если известен anchor_chunk_id (первый chunk секции или chunk_id из hit), иначе принудительно падает на `read_doc_section`.
5. Прогрессивное окно: радиус `R` (per-side). По умолчанию растёт 1 → 2 → ... → `R`, но не превышает `window_radius` и не просит больше, чем разрешено MCP proxy; учитывает prompt tokens + текст из tool-результатов и режет при превышении `context_token_budget`.
6. `mock_mode=true` (дефолт) эмулирует retrieval/LLM/MCP ответы без сетевых вызовов.

## 4. Зависимости
- **Retrieval Service**: `/internal/retrieval/search` (вход: query, tenant_id, фильтры) → hits/steps.
- **LLM runtime** (через LLM Service клиент): OpenAI-style chat completions.
- **MCP Tools Proxy**: `read_chunk_window`, `read_doc_section`.

## 5. Конфигурация (`ORCH_*`)
`retrieval_url`, `mcp_proxy_url`, `llm_runtime_url`, `default_model`, `prompt_token_budget`, `context_token_budget`, `max_tool_steps`, `window_radius` (`RAG_WINDOW_RADIUS`/`ORCH_WINDOW_RADIUS`, легаси `window_max`/`MCP_PROXY_MAX_CHUNK_WINDOW` → `min(window_max, floor((total-1)/2))`), `retry_attempts`, `mock_mode`, `host/port/log_level`.

## 6. Ограничения
- Output safety не вызывается (пока) — отвечает только input safety от Gateway.
- Нет сохранения истории диалога; каждое обращение stateless.
- Трассировка/метрики — только структурные логи (`structlog`).

## 7. Тестирование
- Юниты в `services/ai_orchestrator/tests` проверяют построение контекста и tool-loop в mock режиме.
- E2E — `tests/test_pipeline_integration.py` через ASGITransport (mock стэк).
