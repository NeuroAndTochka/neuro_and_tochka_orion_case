## Orion Soft Internal AI Assistant a.k.a `Visior`

---

## 0. Conventions

- All requests are JSON over HTTPS, unless указано иное.
- Charset: UTF‑8.
- Versioning: `/api/v1/...` для public API.
- Correlation:
  - `X-Request-ID` — обязательный trace ID от gateway.
- Auth:
  - `Authorization: Bearer <token>` (или другой корпоративный механизм).

### 0.1 Common Error Format
```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human-readable explanation",
    "details": {
      "field": "optional structured info"
    }
  },
  "trace_id": "uuid-or-trace"
}
````
---

# 1. Public API — Frontend ↔ Backend (API Gateway)

Все эти эндпоинты видит фронт. Внутри API Gateway может звать другие сервисы, но фронту это не важно.

Базовый префикс: `/api/v1`

---

## 1.1 Authentication & Session

> Вариант: если аутентификация делается не через этот backend, этот раздел можно опустить / адаптировать.

### 1.1.1 `GET /api/v1/auth/me`

Вернуть информацию о текущем пользователе и его правах.

Headers:

- Authorization: Bearer <token>

Response 200:
```json
{
  "user_id": "u_123",
  "username": "parlay06",
  "display_name": "Parlay",
  "roles": ["user"],
  "tenant_id": "tenant_1"
}
```
---

## 1.2 Assistant Chat / Q&A

### 1.2.1 `POST /api/v1/assistant/query`

Основной эндпоинт для фронта: задать вопрос ассистенту.

Headers:

- Authorization: Bearer <token>
- X-Request-ID: <uuid> (опционально, если фронт умеет)

Request body:
```json
{
  "query": "How to configure LDAP integration in Orion soft X?",
  "language": "en",
  "context": {
    "channel": "web",
    "ui_session_id": "sess_123",
    "conversation_id": "conv_42"
  }
}
```
Response 200:
```json
{
  "answer": "To configure LDAP integration in Orion soft X, you should...",
  "sources": [
    {
      "doc_id": "doc_123",
      "doc_title": "Product X Admin Guide",
      "section_id": "sec_ldap",
      "section_title": "LDAP Configuration",
      "page_start": 6,
      "page_end": 7
    }
  ],
  "meta": {
    "latency_ms": 1450,
    "trace_id": "abc-def-123",
    "safety": {
      "input": "allowed",
      "output": "allowed"
    }
  }
}
```
---

## 1.3 Documents Management (Upload / Status / List)

Документы загружаются через API Gateway, далее ingestion работает асинхронно.

### 1.3.1 `POST /api/v1/documents/upload`

Загрузка нового документа для индексации.

Тип запроса: multipart/form-data

Fields:

- file: бинарник PDF/Docx.
- product (optional): строка, напр. "Orion X".
- version (optional): напр. "1.2".
- tags (optional): JSON‑строка со списком тегов.

Response 202:
```json
{
  "doc_id": "doc_123",
  "status": "uploaded"
}
```
---

### 1.3.2 `GET /api/v1/documents`

Список документов пользователя/тенанта.

Query params (optional):

- status — фильтр по статусу (uploaded, processing, indexed, failed).
- product, tag, search — фильтры/поиск.

Response 200:
```json
[
  {
    "doc_id": "doc_123",
    "name": "Orion_X_Admin_Guide.pdf",
    "status": "indexed",
    "product": "Orion X",
    "version": "1.2",
    "tags": ["admin", "ldap"],
    "created_at": "2025-12-03T10:15:00Z",
    "updated_at": "2025-12-03T10:20:00Z"
  },
  {
    "doc_id": "doc_124",
    "name": "API_Reference.pdf",
    "status": "processing",
    "product": "Orion API"
  }
]
```
---

### 1.3.3 `GET /api/v1/documents/{doc_id}`

Детали документа.

Response 200:
```json
{
  "doc_id": "doc_123",
  "name": "Orion_X_Admin_Guide.pdf",
  "status": "indexed",
  "product": "Orion X",
  "version": "1.2",
  "tags": ["admin", "ldap"],
  "pages": 120,
  "sections": [
    {
      "section_id": "sec_1",
      "title": "Overview",
      "page_start": 1,
      "page_end": 3
    },
    {
      "section_id": "sec_ldap",
      "title": "LDAP Configuration",
      "page_start": 6,
      "page_end": 12
    }
  ]
}
```
---

### 1.3.4 `GET /api/v1/documents/{doc_id}/status`

Упрощённый эндпоинт для polling статуса ingestion.

Response 200:
```json
{
  "doc_id": "doc_123",
  "status": "indexed",
  "last_error": null
}
```
---

## 1.4 Health & Diagnostics

### 1.4.1 `GET /api/v1/health`

Простой healthcheck для фронта/мониторинга.

Response 200:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "time": "2025-12-04T12:00:00Z"
}
```
---

# 2. Internal APIs — Inter‑Service Calls

Все internal‑эндпоинты можно держать под префиксом /internal/...
Они не должны быть доступны извне (только через private network / service‑mesh).

---

## 2.1 AI Orchestrator API

### 2.1.1 `POST /internal/ai/query`

Request body:
```json
{
  "user": {
    "user_id": "u_123",
    "tenant_id": "tenant_1",
    "roles": ["user"]
  },
  "query": "How to configure LDAP integration in Orion soft X?",
  "language": "en",
  "context": {
    "channel": "web",
    "conversation_id": "conv_42"
  },
  "trace_id": "abc-def-123"
}
```
Response:
```json
{
  "answer": "To configure LDAP integration...",
  "sources": [
    {
      "doc_id": "doc_123",
      "section_id": "sec_ldap",
      "page_start": 6,
      "page_end": 7
    }
  ],
  "meta": {
    "latency_ms": 1450,
    "safety_input": "allowed",
    "safety_output": "allowed"
  }
}
```
---

## 2.2 Safety Service API

Базовый префикс: /internal/safety

### 2.2.1 `POST /internal/safety/input-check`

Request:
```json
{
  "user": {
    "user_id": "u_123",
    "tenant_id": "tenant_1",
    "roles": ["user"]
  },
  "query": "How to hack Orion soft servers?",
  "channel": "web",
  "trace_id": "abc-def-123"
}
```
Response (пример блокировки):
```json
{
  "status": "blocked",
  "reason": "disallowed_content",
  "message": "This request violates security policy.",
  "transformed_query": null
}
```
Response (пример transform):
```json
{
  "status": "transformed",
  "reason": "pii_sanitized",
  "message": "Sensitive data removed from query.",
  "transformed_query": "How to configure LDAP integration?"
}
```
---

### 2.2.2 `POST /internal/safety/output-check`

Request:
```json
{
  "user": {
    "user_id": "u_123",
    "tenant_id": "tenant_1",
    "roles": ["user"]
  },
  "query": "How to configure LDAP integration?",
  "answer": "Full answer text from LLM...",
  "sources": [
    {
      "doc_id": "doc_123",
      "section_id": "sec_ldap",
      "page_start": 6,
      "page_end": 7
    }
  ],
  "trace_id": "abc-def-123"
}
```
Response (allow):
```json
{
  "status": "allowed",
  "sanitized_answer": null,
  "reason": null
}
```
Response (sanitize):
```json
{
  "status": "sanitized",
  "sanitized_answer": "I cannot provide detailed hacking instructions. However, for secure configuration...",
  "reason": "disallowed_content_trimmed"
}
```
---

## 2.3 Retrieval Service API

Префикс: /internal/retrieval

### 2.3.1 `POST /internal/retrieval/search`

Request:
```json
{
  "query": "How to configure LDAP integration in Orion soft X?",
  "tenant_id": "tenant_1",
  "language": "en",
  "params": {
    "max_docs": 20,
    "max_sections": 50,
    "max_chunks": 40,
    "context_token_limit": 4000
  },
  "trace_id": "abc-def-123"
}
```
Response:
```json
{
  "chunks": [
    {
      "chunk_id": "ch_2001",
      "doc_id": "doc_123",
      "section_id": "sec_ldap",
      "text": "To configure LDAP integration in Orion soft X, you must...",
      "tokens": 350,
      "page_start": 6,
      "page_end": 7,
      "score": 0.92,
      "mcp_link": {
        "doc_id": "doc_123",
        "page_start": 6,
        "page_end": 7
      }
    }
  ],
  "used_docs": [
    {
      "doc_id": "doc_123",
      "score": 0.87
    }
  ],
  "meta": {
    "retrieval_time_ms": 130,
    "trace_id": "abc-def-123"
  }
}
```
---

## 2.4 LLM Service API

Префикс: /internal/llm

### 2.4.1 `POST /internal/llm/generate`

Request:
```json
{
  "mode": "rag",
  "system_prompt": "You are Orion soft internal assistant...",
  "messages": [
    {
      "role": "user",
      "content": "How to configure LDAP integration?"
    }
  ],
  "context_chunks": [
    {
      "doc_id": "doc_123",
      "section_id": "sec_ldap",
      "text": "To configure LDAP integration in Orion soft X, you must...",
      "page_start": 6,
      "page_end": 7
    }
  ],
  "generation_params": {
    "max_tokens": 512,
    "temperature": 0.2,
    "top_p": 0.9
  },
  "trace_id": "abc-def-123"
}
```
Response:
```json
{
  "answer": "To configure LDAP integration in Orion soft X, you should...",
  "used_tokens": {
    "prompt": 1200,
    "completion": 220
  },
  "tools_called": [
    {
      "name": "read_doc_section",
      "arguments": {
        "doc_id": "doc_123",
        "page_start": 6,
        "page_end": 7
      }
    }
  ],
  "meta": {
    "model_name": "local-llama-3-8b",
    "latency_ms": 900,
    "trace_id": "abc-def-123"
  }
}
```
---

## 2.5 Ingestion Service API

Префикс: /internal/ingestion

### 2.5.1 `POST /internal/ingestion/enqueue`

Request:
```json
{
  "doc_id": "doc_123",
  "tenant_id": "tenant_1",
  "file_path": "s3://bucket/orion/doc_123.pdf",
  "product": "Orion X",
  "version": "1.2",
  "tags": ["admin", "ldap"],
  "trace_id": "abc-def-123"
}
```
Response:
```json
{
  "job_id": "ing_456",
  "status": "queued"
}
```
---

## 2.6 Async APIs — Events & Queues

### 2.6.1 Queue: documents_to_ingest
```json
{
  "job_id": "ing_456",
  "doc_id": "doc_123",
  "tenant_id": "tenant_1",
  "file_path": "s3://bucket/orion/doc_123.pdf",
  "created_at": "2025-12-04T10:00:00Z"
}
```
### 2.6.2 Topic: document_ingested
```json
{
  "doc_id": "doc_123",
  "tenant_id": "tenant_1",
  "status": "indexed",
  "sections": 10,
  "chunks": 120,
  "duration_ms": 3500
}
```
### 2.6.3 Topic: ingestion_failed
```json
{
  "doc_id": "doc_124",
  "tenant_id": "tenant_1",
  "status": "failed",
  "error": "PDF parse error: corrupted file",
  "attempts": 3
}
```
---

## 3. Summary

- Part 1 (Public API): фронт ↔ backend через /api/v1/...
- Part 2 (Internal API): контракты между AI Orchestrator, Safety, Retrieval, LLM и Ingestion.
- Async модель: ingestion и события через брокер сообщений.
