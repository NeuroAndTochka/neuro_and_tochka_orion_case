# Техническая спецификация — LLM Service

## 1. Назначение
Обёртка вокруг OpenAI-совместимого chat runtime с поддержкой MCP tool-calls. Принимает `GenerateRequest` (RAG режим), управляет количеством шагов инструментов и возвращает usage/trace.

## 2. API
### `POST /internal/llm/generate`
Request:
```json
{
  "mode": "rag",
  "system_prompt": "You are Visior...",
  "messages": [{"role": "user", "content": "..."}],
  "context_chunks": [{"doc_id": "doc_1", "section_id": "sec", "text": "...", "page_start": 1, "page_end": 2}],
  "generation_params": {"top_p": 0.95, "presence_penalty": 0.0, "frequency_penalty": 0.0},
  "trace_id": "trace-123"
}
```
Response:
```json
{
  "answer": "...",
  "used_tokens": {"prompt": 120, "completion": 40},
  "tools_called": [{"name": "read_doc_section", "arguments": {"doc_id": "doc_1", "section_id": "sec"}, "result_summary": "..."}],
  "meta": {"model_name": "gpt-4o-mini", "trace_id": "trace-123", "tool_steps": 1}
}
```
Ошибки: 400 при превышении `max_tool_steps`; 503 если не настроен runtime или MCP proxy.

### `/health`
`{"status":"ok"}`.

## 3. Поведение
- `mock_mode=true` имитирует tool-call/ответ, не обращаясь к внешним сервисам.
- При tool-call отправляет запрос в MCP Tools Proxy (`MCPClient.execute`) с `user_id="llm"`, `tenant_id="tenant"`.
- Сообщения для runtime строятся в `build_rag_prompt`: системный prompt + инструкция скрывать chain-of-thought + блок с контекстными чанками.
- `enable_json_mode` при включении добавляет `response_format={type: json_object}` в payload.

## 4. Конфигурация (`LLM_SERVICE_*`)
`llm_runtime_url`, `default_model`, `max_tool_steps`, `enable_json_mode`, `mcp_proxy_url`, `mock_mode`, `host/port/log_level`.

## 5. Ограничения и планы
- Нет встроенного safety; ответственность на внешних слоях.
- Для прод-режима нужен доступный OpenAI-совместимый runtime и MCP proxy URL.
