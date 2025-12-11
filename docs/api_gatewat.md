# Technical Specification (TZ)
## Microservice: **API Gateway**
### Project: Orion Soft Internal AI Assistant — *Visior*

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

# 3. Architecture Overview

API Gateway — stateless HTTP сервис, разворачиваемый как NGINX+Lua, Envoy, или FastAPI proxy layer.
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

# 4. API Endpoints (Public API)

## 4.1 Authentication

### `GET /api/v1/auth/me`
- Validate token
- Return user profile + tenant_id

### `POST /api/v1/auth/refresh` (если используется refresh flow)
- Validate refresh token
- Issue new access token

---

## 4.2 Assistant Query

### `POST /api/v1/assistant/query`

**Flow:**
1. Auth → OK
2. Input Safety Check
3. Route to Orchestrator
4. Receive answer
5. Output formatting

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

## 4.3 Document Upload & Management

### `POST /api/v1/documents/upload`
- multipart/form-data
- file (PDF/Docx)
- metadata fields (product, version, tags)

Internal route: `/internal/ingestion/enqueue`

### `GET /api/v1/documents`
- Query list of documents for tenant

Internal route: `/internal/documents/list`

### `GET /api/v1/documents/{id}`
- Get metadata

---

## 4.4 Healthchecks

### `GET /api/v1/health`
- Returns static OK

---

# 5. Internal Dependencies

API Gateway вызывает следующие микросервисы:

| Service             | Endpoint                                | Purpose |
|--------------------|-------------------------------------------|---------|
| Safety Service     | `/internal/safety/input-check`            | Validation of query |
| AI Orchestrator    | `/internal/ai/query`                      | Main AI pipeline |
| Ingestion Service  | `/internal/ingestion/enqueue`             | Document ingestion |
| Document Service   | `/internal/docs/...`                      | Metadata retrieval |
| Auth Provider      | `/oauth/introspect` / JWKS                | JWT/SSO verification |

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

# 6. Authentication & Authorization

## 6.1 Supported Modes
- **JWT Access Tokens** (preferred)
- **OIDC / OAuth2**
- **SAML (optional)**

## 6.2 JWT Validation
- Проверка подписи через JWKS
- Проверка истечения
- Проверка `issuer`, `audience`

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

## 7.1 Levels
1. per IP
2. per user
3. per tenant
4. per endpoint

## 7.2 Requirements
- Burst limit: 10 req/sec
- Sustained limit: 2 req/sec per user
- Heavy endpoints (`upload`) — отдельные лимиты

## 7.3 Implementation
- FastAPI
- Envoy rate-limit-service
- Redis-based limiter

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
