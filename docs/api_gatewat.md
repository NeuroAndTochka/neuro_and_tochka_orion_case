# Техническая спецификация — API Gateway

## Назначение
Edge-слой платформы: принимает публичные запросы, выполняет простую аутентификацию (mock introspection по умолчанию), rate limiting и input safety, затем проксирует в оркестратор/ингестию/документы.

## Функциональность
- Генерация/прокидывание `X-Request-ID` через `RequestContextMiddleware`.
- `Authorization: Bearer` обязательный для публичных ручек; при `mock_mode=true` возвращается заглушечный пользователь.
- In-memory `RateLimiter` с порогом `API_GATEWAY_RATE_LIMIT_PER_MINUTE`.
- Вызов safety input check перед отправкой запроса ассистенту.

## Публичные эндпоинты (`/api/v1`)
- `GET /health` — `{"status":"ok"}`.
- `GET /auth/me` — профиль пользователя (`user_id`, `username`, `roles`, `tenant_id`, `display_name?`).
- `POST /assistant/query` — принимает `query`, опц. `language`, `context{channel, ui_session_id, conversation_id}`; делает safety input и вызывает оркестратор. Ответ: `answer`, `sources[]`, `meta{trace_id, latency_ms?, safety?}`.
- `POST /documents/upload` — multipart `file` + опц. `product/version/tags`; отправляет в ingestion.
- `GET /documents` — список документов (фильтры `status|product|tag|search`).
- `GET /documents/{doc_id}` — карточка документа.

## Внутренние зависимости
- Safety Service `/internal/safety/input-check`.
- AI Orchestrator `/internal/orchestrator/respond`.
- Ingestion Service `/internal/ingestion/enqueue`.
- Document Service (используется клиентом `DocumentClient`, в коде вызывается `/internal/documents/list`, в проде следует использовать `/internal/documents`).

## Конфигурация (`API_GATEWAY_*`)
- `SAFETY_BASE_URL`, `ORCHESTRATOR_BASE_URL`, `INGESTION_BASE_URL`, `DOCUMENTS_BASE_URL` — base URLs зависимостей.
- `AUTH_INTROSPECTION_URL`, `AUTH_AUDIENCE` — проверка токенов; если не заданы или `mock_mode=true`, возвращается demo user.
- `RATE_LIMIT_PER_MINUTE`, `HTTP_TIMEOUT_SECONDS`, `ALLOWED_ORIGINS`, `MOCK_MODE`.

## Особенности реализации
- Все HTTP клиенты создаются один раз в lifespan и кладутся в `app.state`.
- Trace_id и tenant_id из middleware пробрасываются в `request.state` и заголовки ответов.
- Нет output safety и проверки прав на документы на уровне Gateway — ответственность downstream сервисов.
