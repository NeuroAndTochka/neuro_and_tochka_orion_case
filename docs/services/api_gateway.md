# API Gateway

## Назначение
API Gateway — единственная внешняя точка входа для Orion. Он проверяет аутентификацию, применяет rate limit, связывает клиентский запрос с input safety и передаёт его в AI Orchestrator. Также выступает фронтом для загрузки и просмотра документов.

## Архитектура и зависимости
- **FastAPI приложение** (`services/api_gateway`).
- **HTTP-клиенты**: safety, orchestrator, ingestion, document, auth.
- **Middleware**: `RequestContextMiddleware` генерирует `trace_id` и сохраняет в `request.state`.
- **RateLimiter**: in-memory счётчик с конфигурируемым лимитом.
- **Конфигурация**: `API_GATEWAY_*` (см. `config.py`).

## Конфигурационные переменные
| Переменная | Назначение |
| --- | --- |
| `API_GATEWAY_SAFETY_BASE_URL` | URL input safety. |
| `API_GATEWAY_ORCHESTRATOR_BASE_URL` | URL AI Orchestrator. |
| `API_GATEWAY_DOCUMENTS_BASE_URL` | URL document service. |
| `API_GATEWAY_INGESTION_BASE_URL` | URL ingestion service. |
| `API_GATEWAY_AUTH_INTROSPECTION_URL` | Endpoint для проверки токенов. |
| `API_GATEWAY_RATE_LIMIT_PER_MINUTE` | Глобальный лимит на пользователя. |
| `API_GATEWAY_MOCK_MODE` | Если `true`, клиенты возвращают заглушки. |

## Внешние API
### 1. `GET /api/v1/health`
Проверка живости.

```
curl https://api-gateway/ api/v1/health
```

### 2. `GET /api/v1/auth/me`
Возвращает профиль текущего пользователя.

```
curl -H "Authorization: Bearer <token>" https://gateway/api/v1/auth/me
```

### 3. `POST /api/v1/assistant/query`
Основной endpoint ассистента. Требует заголовок `Authorization` и JSON:

```json
{
  "query": "Расскажи про LDAP",
  "language": "ru",
  "context": {
    "channel": "web",
    "conversation_id": "conv-123"
  }
}
```

Ответ:
```json
{
  "answer": "...",
  "sources": [{"doc_id": "doc_1", "section_id": "sec_intro"}],
  "meta": {
    "latency_ms": 340,
    "trace_id": "trace-abc",
    "safety": {"input": "allowed", "output": "allowed"}
  }
}
```

### 4. `POST /api/v1/documents/upload`
Мультипарт загрузка документа. Прокидывает файлы в ingestion service. В метаданных необходимо указать `product/version/tags` (опционально). Возвращает `job_id` и `doc_id`.

### 5. `GET /api/v1/documents`
Список документов с фильтрами `status`, `product`, `tag`, `search`.

### 6. `GET /api/v1/documents/{doc_id}`
Детальная карточка.

## Взаимодействие с задними сервисами
| Сервис | Endpoint | Примечания |
| --- | --- | --- |
| Safety | `/internal/safety/input-check` | Обязателен `user` блок и `trace_id` в meta. |
| Orchestrator | `/internal/orchestrator/respond` | Передаём `user`, `tenant_id`, `trace_id`, `safety`. |
| Ingestion | `/internal/ingestion/enqueue` | Multipart; требуется `X-Tenant-ID`. |
| Document | `/internal/documents` и т.д. | Все вызовы с заголовком `X-Tenant-ID`. |

## Рекомендации по мокам
- При внедрении новых downstream endpoint'ов обязательно обновляйте соответствующий клиент (`api_gateway/clients/*`) и добавляйте mock реализацию (условный `if self.mock_mode`).
- Для локальной разработки можно переключить `API_GATEWAY_MOCK_MODE=true`. Тогда ассистент будет возвращать статический ответ, но структура payload должна полностью соответствовать прод версии.
- Любое изменение формы ответа необходимо сразу отражать: 1) в Pydantic схемах (`schemas.py`), 2) в этом документе и 3) в e2e тесте `tests/test_pipeline_integration.py`.
