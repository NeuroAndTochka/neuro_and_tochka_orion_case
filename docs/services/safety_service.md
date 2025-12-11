# Safety Service

## Назначение
Safety Service реализует input guard и output guard, применяя комбинированные правила (блок-листы, PII, prompt-injection) и возвращая нормализованный `SafetyResponse`. Сервис вызывается API Gateway (input) и AI Orchestrator (output).

## Архитектура
- FastAPI (`services/safety_service`).
- Основная логика — `core/evaluator.py`.
- Конфиг `SAFETY_SERVICE_*` управляет политикой, блоклистом и режимом санитайза.

## Конфигурация
| Переменная | Описание |
| --- | --- |
| `SAFETY_SERVICE_POLICY_MODE` | `strict/balanced/relaxed` — влияет на реакцию на PII. |
| `SAFETY_SERVICE_BLOCKLIST` | Список запрещённых слов/шаблонов. |
| `SAFETY_SERVICE_ENABLE_PII_SANITIZE` | Флаг редактирования текста. |
| `SAFETY_SERVICE_DEFAULT_POLICY_ID` | Идентификатор политики в логах. |

## API
### `POST /internal/safety/input-check`
**Request**
```json
{
  "user": {"user_id": "demo", "tenant_id": "tenant_1", "roles": ["agent"]},
  "query": "Расскажи про LDAP",
  "channel": "web",
  "context": {"conversation_id": "conv-1"},
  "meta": {"trace_id": "trace-abc"}
}
```
**Response**
```json
{
  "status": "allowed",
  "reason": "clean",
  "policy_id": "policy_default_v1",
  "trace_id": "trace-abc",
  "risk_tags": []
}
```

### `POST /internal/safety/output-check`
**Request**
```json
{
  "user": {"user_id": "demo", "tenant_id": "tenant_1"},
  "query": "Расскажи про LDAP",
  "answer": "LDAP — ...",
  "sources": [{"doc_id": "doc_1", "section_id": "sec_intro"}],
  "meta": {"trace_id": "trace-abc"}
}
```
**Response** такой же формат `SafetyResponse`. При `status=transformed` присутствует `transformed_answer`.

## Расширение
- Добавляя новое правило, фиксируйте его в `evaluate_input`/`evaluate_output` и покрывайте тестами (`tests/test_evaluator.py`).
- Если меняется структура `SafetyResponse`, нужно обновить `safety_service/schemas.py`, клиентов API Gateway/Orchestrator и интеграционные тесты.

## Моки
- Все клиенты должны уважать возможные статусы: `allowed`, `transformed`, `blocked`, `monitor` (добавьте при появлении).
- В mock-режиме сервис может отвечать статически, но поля `status/reason/policy_id/trace_id` обязательны. При изменении формата необходимо синхронное обновление `api_gateway.clients.safety` и `ai_orchestrator.clients.safety`.

