# LLM Service

## Назначение
LLM Service инкапсулирует работу с LLM runtime и MCP-инструментами. Он принимает подготовленный RAG-запрос от оркестратора, строит промпт, управляет итерациями tool-call'ов и возвращает нормализованный `GenerateResponse`.

## Архитектура
- FastAPI приложение (`services/llm_service`).
- `core/orchestrator.LLMOrchestrator` — главный класс сервиса.
- Клиенты: `LLMRuntimeClient`, `MCPClient`.
- Конфиг через `LLM_SERVICE_*`.

## Конфигурация
| Переменная | Описание |
| --- | --- |
| `LLM_SERVICE_LLM_RUNTIME_URL` | Endpoint модели. |
| `LLM_SERVICE_DEFAULT_MODEL` | Идентификатор модели по умолчанию. |
| `LLM_SERVICE_MAX_TOOL_STEPS` | Лимит итераций tool-call. |
| `LLM_SERVICE_MAX_COMPLETION_TOKENS` | Максимум токенов в ответе. |
| `LLM_SERVICE_ENABLE_JSON_MODE` | Принудительный json-ответ. |
| `LLM_SERVICE_MCP_PROXY_URL` | URL призна инструментов. |
| `LLM_SERVICE_MOCK_MODE` | Возвращать заглушки.

## API
### `POST /internal/llm/generate`
**Request**
```json
{
  "mode": "rag",
  "system_prompt": "You are Orion",
  "messages": [
    {"role": "user", "content": "Расскажи про LDAP"}
  ],
  "context_chunks": [
    {
      "doc_id": "doc_1",
      "section_id": "sec_intro",
      "text": "LDAP — Lightweight...",
      "page_start": 1,
      "page_end": 2
    }
  ],
  "generation_params": {
    "max_tokens": 400,
    "temperature": 0.2
  },
  "trace_id": "trace-abc"
}
```
**Response**
```json
{
  "answer": "LDAP — ...",
  "used_tokens": {"prompt": 120, "completion": 85},
  "tools_called": [
    {
      "name": "read_doc_section",
      "arguments": {"doc_id": "doc_1", "section_id": "sec_intro"},
      "result_summary": "2 pages"
    }
  ],
  "meta": {
    "model_name": "gpt-4o-mini",
    "trace_id": "trace-abc",
    "tool_steps": 1
  }
}
```

## MCP инструменты
- Реестр объявлен в `mcp_tools_proxy`. LLM Service лишь инициирует вызовы по именам.
- Каждый tool-call возвращает `status` и `result`. Следите, чтобы `result_summary` был строкой (используется UI).

## Расширение
- Для новых режимов промпта добавляйте функции в `core/prompt.py` и прокидывайте флаги через `GenerateRequest`.
- При добавлении новых параметров генерации обновляйте `schemas.py`, `GenerationParams` и OpenAPI.

## Mock требования
- Mock payload должен включать корректные структуры `used_tokens`, `tools_called`, `meta`.
- Если вы добавляете дополнительное поле в ответ (например, `confidence`), сразу добавьте значение в mock (`LLMRuntimeClient._mock_response`) и тесты.
