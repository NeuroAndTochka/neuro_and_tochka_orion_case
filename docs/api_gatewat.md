# Техническая спецификация (ТЗ)
## Микросервис: **API Gateway**
### Проект: Orion Soft Internal AI Assistant — *Visior*

---

# 1. Purpose of the Service

API Gateway является единым входным узлом для всех внешних запросов к платформе Visior.
Он обеспечивает:
- маршрутизацию,
- аутентификацию и авторизацию,
- rate limiting,
- входной safety-контур,
- аудит и трассировку,
- унифицированный API для фронтенда и интеграций.

Gateway не содержит бизнес-логики ассистента — только функции edge layer.

---

# 2. Responsibilities (Scope)

## 2.1 Primary Responsibilities
1. Приём всех HTTP-запросов клиентов/интеграций.
2. Проверка аутентификации (JWT / OAuth2 / SSO).
3. Верификация tenant context и прав пользователя.
4. Генерация `trace_id` для всей цепочки вызовов.
5. Rate limiting (per tenant / per user / per IP).
6. Input Safety Filter (вызов safety service).
7. Валидация структуры входных данных.
8. Маршрутизация запросов по микросервисам:
   - AI Orchestrator
   - Ingestion Service
   - Document Service
9. Обёртка ошибок в единый формат (`error.code`, `trace_id`).
10. Логирование запросов и ответов без PII.

## 2.2 Out of Scope
- RAG-инференс
- LLM вызовы
- чтение документов
- обработка файлов
- генерация ответов
- chunking, ingestion, embeddings

---

# 3. Обзор архитектуры

API Gateway — stateless HTTP‑сервис, который можно развернуть как NGINX+Lua, Envoy или FastAPI proxy layer.
Поддерживает горизонтальное масштабирование без сохранения внутреннего состояния.

```
Client
   ↓
API Gateway
   ↓  (auth + safety + routing)
Orchestrator / Ingestion / Documents / Safety
```

Сервис должен быть совместим с:
- Kubernetes Ingress
- Istio / Linkerd сервис-меш
- OPA / Rego policies (опционально)

---

# 4. Публичные endpoint'ы

## 4.1 Аутентификация

### `GET /api/v1/auth/me`
- Проверить токен.
- Вернуть профиль пользователя вместе с `tenant_id`.

### `POST /api/v1/auth/refresh` (если используется refresh flow)
- Проверить refresh token.
- Выдать новую пару токенов.

---

## 4.2 Запрос ассистента

### `POST /api/v1/assistant/query`

**Flow:**
1. Проверить авторизацию.
2. Вызвать input safety.
3. Передать запрос в Orchestrator.
4. Получить ответ.
5. Сформировать payload для фронта.

**Request**:
```json
{
  "query": "...",
  "language": "ru",
  "context": {
    "conversation_id": "conv_123",
    "channel": "web"
  }
}
```

**Response**:
```json
{
  "answer": "...",
  "sources": [...],
  "meta": {
    "trace_id": "abc",
    "latency_ms": 1234
  }
}
```

---

## 4.3 Загрузка и управление документами

### `POST /api/v1/documents/upload`
- multipart/form-data.
- обязательное поле `file` (PDF/DOCX).
- метаданные `product`, `version`, `tags`.

Internal route: `/internal/ingestion/enqueue`

### `GET /api/v1/documents`
- Вернуть список документов для текущего tenant.

Internal route: `/internal/documents/list`

### `GET /api/v1/documents/{id}`
- Вернуть метаданные конкретного документа.

---

## 4.4 Health

### `GET /api/v1/health`
- Возвращает статический `{\"status\":\"ok\"}`.

---

# 5. Internal Dependencies

API Gateway вызывает следующие микросервисы:

| Service             | Endpoint                                | Назначение |
|--------------------|-------------------------------------------|------------|
| Safety Service     | `/internal/safety/input-check`            | Проверка запросов |
| AI Orchestrator    | `/internal/ai/query`                      | Основной AI-пайплайн |
| Ingestion Service  | `/internal/ingestion/enqueue`             | Постановка документов в обработку |
| Document Service   | `/internal/docs/...`                      | Получение метаданных |
| Auth Provider      | `/oauth/introspect` / JWKS                | Проверка JWT/SSO |

Все вызовы должны содержать:
- `X-Request-ID` (trace_id)
- `X-Tenant-ID`

---

# 6. Implementation Notes

Скелет микросервиса расположен в `services/api_gateway` и разворачивается как FastAPI-приложение.

- точка входа: `api_gateway.main:app`
- конфиг через `API_GATEWAY_*` переменные (`config.py`)
- внешние вызовы оформлены в клиентах (`api_gateway/clients/*`) и автоматически добавляют `X-Request-ID`, `X-Tenant-ID`, `X-User-ID`
- включён базовый rate limiting per tenant/user и mock-режим (`API_GATEWAY_MOCK_MODE=true`) для локальной разработки без доступных бэкендов

---

# 6. Аутентификация и авторизация

## 6.1 Поддерживаемые режимы
- **JWT Access Tokens** (основной режим).
- **OIDC / OAuth2**.
- **SAML** (опционально).

## 6.2 Проверка JWT
- Проверка подписи через JWKS.
- Проверка срока действия.
- Проверка `issuer` и `audience`.

## 6.3 Tenant Isolation
Каждый запрос содержит:
- `tenant_id` в JWT claim
или
- подменяется gateway согласно domain mapping

Нельзя допустить:
- межтенантный доступ
- утечку данных другого клиента

---

# 7. Rate Limiting

## 7.1 Уровни
1. по IP;
2. по пользователю;
3. по tenant;
4. по endpoint.

## 7.2 Требования
- краткосрочный лимит: 10 запросов/сек;
- долгосрочный лимит: 2 запрос/сек на пользователя;
- тяжёлые endpoint'ы (`upload`) — отдельные лимиты.

## 7.3 Реализация
- встроенный FastAPI-лимитер;
- Envoy rate-limit-service;
- Redis как хранилище счётчиков.

---

# 8. Input Safety Integration

Каждый запрос к `/assistant/query` проходит safety-проверку.

## 8.1 Flow
1. Gateway получает запрос
2. Извлекает текст `query`
3. Формирует payload:
```json
{
  "user": {...},
  "query": "...",
  "trace_id": "abc"
}
```
4. Отправляет в Safety Service
5. Поведение:
   - `allowed` → пропускаем
   - `transformed` → заменяем запрос
   - `blocked` → возвращаем ошибку

## 8.2 Error Format (при блокировке)
```json
{
  "error": {
    "code": "INPUT_BLOCKED",
    "message": "Query violates safety policy."
  },
  "trace_id": "abc"
}
```

---

# 9. Logging & Audit

## 9.1 Required Log Fields
- timestamp
- service: "gateway"
- trace_id
- user_id
- tenant_id
- endpoint
- HTTP status
- response latency

## 9.2 PII Restrictions
В логах нельзя хранить:
- исходный текст query
- документы
- файлы
- токены

Вместо текста query логируем только intent tags (из safety).

---

# 10. Error Handling

Все ошибки должны быть приведены к единому формату:

```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "Invalid payload",
    "details": {}
  },
  "trace_id": "abc"
}
```

## 10.1 Error Codes
- `UNAUTHORIZED`
- `FORBIDDEN`
- `RATE_LIMITED`
- `INPUT_BLOCKED`
- `INVALID_PAYLOAD`
- `SERVICE_UNAVAILABLE`
- `INTERNAL_ERROR`

---

# 11. Performance Requirements

| Operation               | Latency Target |
|-------------------------|----------------|
| Auth check              | ≤ 20 ms        |
| Input safety call       | ≤ 50 ms        |
| Routing to orchestrator | ≤ 10 ms        |
| Upload → enqueue        | ≤ 100 ms       |

---

# 12. Deployment & Scaling

## 12.1 Horizontal Scaling
Gateway должен быть stateless → масштабируется независимо.

## 12.2 Recommended Instances
- min 3 pods
- autoscale от CPU 60%

## 12.3 Protocols
- HTTP/1.1
- HTTP/2 optional
- gRPC passthrough optional

---

# 13. Configuration

### 13.1 Environment Variables
- `JWT_ISSUER`
- `JWKS_URL`
- `SAFETY_URL`
- `ORCHESTRATOR_URL`
- `INGESTION_URL`
- `RATE_LIMIT_CONFIG`
- `LOG_LEVEL`
- `TRUSTED_PROXIES`

### 13.2 Secrets
- TLS certs
- Signing keys
- OAuth client secrets

---

# 14. Healthchecks

## Liveness
`/internal/health/live`
Always returns OK unless crashed.

## Readiness
`/internal/health/ready`
Checks:
- JWKS reachable
- safety service reachable
- orchestrator reachable

---

# 15. Open Questions

1. Нужна ли поддержка GraphQL?
2. Нужна ли загрузка файлов через resumable upload?
3. Нужны ли индивидуальные policies на уровне tenant?
4. Должны ли интеграции использовать API keys?

---

# END OF DOCUMENT
