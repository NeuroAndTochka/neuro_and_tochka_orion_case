# MCP Tools Proxy

## Назначение
MCP Tools Proxy — прослойка между LLM Service и корпоративными источниками данных. Он реализует Model Context Protocol, проверяет разрешения пользователя и накладывает лимиты на вызовы инструментов.

## Архитектура
- FastAPI приложение (`services/mcp_tools_proxy`).
- Реестр инструментов (`core/executor.ToolRegistry`).
- Встроенные инструменты расположены в `tools/` (например, `local_search`).
- Конфигурация через `MCP_PROXY_*`.

## Конфигурация
| Переменная | Описание |
| --- | --- |
| `MCP_PROXY_MAX_PAGES_PER_CALL` | Ограничение на выдачу документов. |
| `MCP_PROXY_MAX_TEXT_BYTES` | Ограничение на payload в байтах. |
| `MCP_PROXY_RATE_LIMIT_CALLS` | Кол-во вызовов в минуту на пользователя. |
| `MCP_PROXY_RATE_LIMIT_TOKENS` | Ограничение на суммарный размер ответов. |
| `MCP_PROXY_BLOCKLIST_KEYWORDS` | Слова, запрещённые в аргументах. |
| `MCP_PROXY_MOCK_MODE` | Возвращать заглушки. |

## API
### `POST /internal/mcp/execute`
**Request**
```json
{
  "tool": "local_search",
  "arguments": {"query": "LDAP"},
  "user": {"user_id": "demo", "tenant_id": "tenant_1"},
  "trace_id": "trace-abc"
}
```
**Response**
```json
{
  "status": "ok",
  "result": {
    "chunks": [
      {"doc_id": "doc_1", "section_id": "sec_intro", "text": "LDAP ..."}
    ]
  },
  "metrics": {"duration_ms": 45}
}
```
В случае ошибок `status="error"` и поле `error` содержит описание.

## Расширение
1. Добавьте новый модуль в `tools/` и регистрируйте его в `core/executor.py`.
2. Обновите документацию ниже и README сервиса.
3. Напишите интеграционные тесты (`services/mcp_tools_proxy/tests`).

## Mock требования
- При mock_mode каждый инструмент обязан возвращать структуру с ключами `status`, `result`, `metrics`, даже если `result` пустой.
- При изменении API инструмента необходимо синхронно обновить mock-данные в LLM Service (чтобы tool traces отображались корректно).
