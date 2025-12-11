# AI Orchestrator

## Назначение
Оркестратор управляет RAG-пайплайном: проверяет входные данные, запрашивает релевантный контекст из retrieval service, формирует payload для LLM service, проверяет выход через safety и строит ответ с телеметрией. Endpoint вызывается только API Gateway.

## Архитектура
- FastAPI (`services/ai_orchestrator`).
- Основной класс `core/orchestrator.Orchestrator` использует клиентов retrieval/llm/safety.
- Конфигурация через `ORCH_*`.

## Конфигурационные параметры
| Переменная | Назначение |
| --- | --- |
| `ORCH_RETRIEVAL_URL` | URL поиска. |
| `ORCH_LLM_URL` | URL генерации ответа. |
| `ORCH_SAFETY_URL` | URL output safety. |
| `ORCH_PROMPT_TOKEN_BUDGET` | Ограничение на контекст. |
| `ORCH_MOCK_MODE` | Позволяет вернуть готовый ответ без сетевых вызовов. |

## API
### `POST /internal/orchestrator/respond`
**Request**
```json
{
  "query": "Расскажи про LDAP",
  "trace_id": "trace-abc",
  "tenant_id": "tenant_1",
  "user": {
    "user_id": "demo",
    "tenant_id": "tenant_1",
    "roles": ["user"]
  },
  "safety": {"status": "allowed"}
}
```
**Response**
```json
{
  "answer": "LDAP — это ...",
  "sources": [
    {"doc_id": "doc_1", "section_id": "sec_intro", "page_start": 1, "page_end": 2}
  ],
  "safety": {"input": "allowed", "output": "allowed"},
  "telemetry": {
    "trace_id": "trace-abc",
    "retrieval_latency_ms": 103,
    "llm_latency_ms": 210,
    "tool_steps": 0
  }
}
```

## Зависимости
1. **Retrieval service** — ожидает `{"query", "tenant_id", "max_results?"}` и возвращает `{"hits": [...]}`. Оркестратор приводить ответ к списку словарей.
2. **LLM service** — payload формируется в `_build_llm_payload`; любые изменения структуры нужно согласовать с LLM командой.
3. **Safety service (output)** — отправляем `user`, `query`, `answer`, `sources`, `meta.trace_id`.

## Расширение
- Поддержка новых режимов (например, tool-use) добавляется через настраиваемые стратегии в `core/orchestrator.py` и `schemas.py`.
- При изменении формата `OrchestratorResponse` все клиенты (API Gateway, интеграционные тесты) должны обновиться одновременно.
- Для mock режима рекомендуется использовать отдельные fixtures или dependency overrides, но структура ответа должна оставаться неизменной.

## Mock требования
- Любой новый ключ в response должен иметь default в mock payload, иначе API Gateway может упасть при сериализации.
- Для unit-тестов (например `services/ai_orchestrator/tests/test_respond.py`) используйте `Settings(mock_mode=True)` и кастомные httpx mock-транспорты, чтобы зафиксировать контракт.

