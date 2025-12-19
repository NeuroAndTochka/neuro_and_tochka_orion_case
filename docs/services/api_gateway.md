# API Gateway

## Назначение
Публичный слой (`/api/v1`) для ассистента: auth, rate limit, input safety и прокси в оркестратор/ингестию/документы. Работает на FastAPI (`services/api_gateway`).

## Эндпоинты
- `GET /api/v1/health`.
- `GET /api/v1/auth/me` — профиль пользователя (mock при `mock_mode=true`).
- `POST /api/v1/assistant/query` — вызывает safety input и AI Orchestrator, возвращает `answer`, `sources`, `meta.trace_id`.
- `POST /api/v1/documents/upload` — multipart upload → Ingestion Service.
- `GET /api/v1/documents`, `GET /api/v1/documents/{doc_id}` — прокси в Document Service (в коде используется клиент к `/internal/documents/list`).

## Зависимости
Safety, Orchestrator, Ingestion, Document Service вызываются через httpx-клиенты из `api_gateway/clients`. `RequestContextMiddleware` создаёт trace_id и сохраняет tenant_id, rate limiter — in-memory.

## Конфигурация
`API_GATEWAY_*`: base URLs зависимостей, `auth_introspection_url` + `auth_audience`, `http_timeout_seconds`, `rate_limit_per_minute`, `allowed_origins`, `mock_mode`.

## Особенности
- При отсутствии introspection URL или в `mock_mode` AuthClient возвращает пользователя `demo` с tenant `demo`.
- Trace_id доступен через `meta.trace_id` в ответе ассистента и ставится в `X-Request-ID` заголовок.
- Output safety не вызывается на этом уровне; downstream сервисы проверяют права на документы/тенанты.
