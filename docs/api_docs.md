# Документация по API Orion Soft — Visior

Документ описывает все внешние (`/api/v1/...`) и внутренние (`/internal/...`) HTTP‑контракты платформы. Все примеры приведены в формате JSON, поля и названия endpoint'ов иллюстрируют финальные продовые значения.

## 0. Общие правила
- Передача данных: JSON поверх HTTPS, кодировка UTF‑8.
- Версионирование: публичные URL начинаются с `/api/v1`, внутренние — с `/internal`.
- Корреляция запросов: используем заголовок `X-Request-ID` (его генерирует API Gateway и прокидывает вниз по цепочке).
- Аутентификация: заголовок `Authorization: Bearer <token>`; внутренние сервисы могут дополнительно использовать сервисные токены.

### 0.1 Формат ошибки
```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Короткое описание проблемы",
    "details": {
      "field": "опциональные детали"
    }
  },
  "trace_id": "uuid-or-trace"
}
```

---

# 1. Публичный API (Frontend ↔ API Gateway)
Базовый префикс: `/api/v1`. Эти эндпоинты доступны клиентским приложениям и интеграциям.

## 1.1 Аутентификация
### `GET /api/v1/auth/me`
Возвращает профиль текущего пользователя.

**Заголовки**
- `Authorization: Bearer <token>`

**Ответ 200**
```json
{
  "user_id": "u_123",
  "username": "parlay06",
  "display_name": "Parlay",
  "roles": ["user"],
  "tenant_id": "tenant_1"
}
```

### `POST /api/v1/auth/refresh` (если используется refresh-flow)
Принимает refresh token и возвращает новую пару `access_token` / `refresh_token`.

## 1.2 Ассистент
### `POST /api/v1/assistant/query`
Основной чат-эндпоинт. Перед вызовом требуется пройти rate limit и input safety.

**Заголовки**
- `Authorization: Bearer <token>`
- `X-Request-ID: <uuid>` (опционально, если генерируется на клиенте)

**Request**
```json
{
  "query": "Расскажи, как настроить LDAP в Orion X",
  "language": "ru",
  "context": {
    "channel": "web",
    "ui_session_id": "sess_123",
    "conversation_id": "conv_42"
  }
}
```

**Response 200**
```json
{
  "answer": "Чтобы настроить LDAP в Orion X, выполните...",
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

## 1.3 Управление документами
### `POST /api/v1/documents/upload`
Загрузка нового документа. Тип запроса — `multipart/form-data`.

**Поля формы**
- `file` — обязательный PDF/DOCX.
- `product`, `version`, `tags` — опциональные метаданные.

**Response 202**
```json
{
  "doc_id": "doc_123",
  "status": "uploaded"
}
```

### `GET /api/v1/documents`
Возвращает список документов арендатора.

**Параметры** `status`, `product`, `tag`, `search` (опционально).

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
  }
]
```

### `GET /api/v1/documents/{doc_id}`
Детальная карточка документа (включая секции и страницы).

### `GET /api/v1/documents/{doc_id}/status`
Упрощённый endpoint для периодического запроса статуса ingestion.

## 1.4 Health
### `GET /api/v1/health`
Простой ответ для мониторинга.
```json
{
  "status": "ok",
  "version": "1.0.0",
  "time": "2025-12-04T12:00:00Z"
}
```

---

# 2. Внутренние API (Service ↔ Service)
Эти endpoint'ы закрыты сетью или mesh'ем и доступны только другим микросервисам.

## 2.1 AI Orchestrator
### `POST /internal/orchestrator/respond`
Получает запрос от Gateway и orchestrat'ит RAG‑пайплайн.
```json
{
  "user": {
    "user_id": "u_123",
    "tenant_id": "tenant_1",
    "roles": ["user"]
  },
  "query": "Как настроить LDAP?",
  "language": "ru",
  "context": {
    "channel": "web",
    "conversation_id": "conv_42"
  },
  "trace_id": "abc-def-123"
}
```
Ответ содержит `answer`, `sources`, `safety`, `telemetry`.

## 2.2 Safety Service
Префикс `/internal/safety`.

### `POST /internal/safety/input-check`
Проверяет пользовательский вопрос.
```json
{
  "user": {"user_id": "u_123", "tenant_id": "tenant_1", "roles": ["user"]},
  "query": "Как взломать Orion?",
  "channel": "web",
  "trace_id": "abc-def-123"
}
```
Ответ:
```json
{
  "status": "blocked",
  "reason": "disallowed_content",
  "message": "Запрос нарушает политику",
  "transformed_query": null
}
```

### `POST /internal/safety/output-check`
Проверяет ответ модели перед выдачей. При `status="sanitized"` возвращает `sanitized_answer`.

## 2.3 Retrieval Service
### `POST /internal/retrieval/search`
```json
{
  "query": "LDAP в Orion",
  "tenant_id": "tenant_1",
  "language": "ru",
  "params": {
    "max_docs": 20,
    "max_sections": 50,
    "max_chunks": 40,
    "context_token_limit": 4000
  },
  "trace_id": "abc-def-123"
}
```
**Response** содержит массив `chunks`, список `used_docs` и `meta.retrieval_time_ms`.

## 2.4 LLM Service
### `POST /internal/llm/generate`
```json
{
  "mode": "rag",
  "system_prompt": "You are Orion soft internal assistant...",
  "messages": [{"role": "user", "content": "Как настроить LDAP?"}],
  "context_chunks": [{"doc_id": "doc_123", "section_id": "sec_ldap", "text": "...", "page_start": 6, "page_end": 7}],
  "generation_params": {"max_tokens": 512, "temperature": 0.2, "top_p": 0.9},
  "trace_id": "abc-def-123"
}
```
Ответ содержит `answer`, `used_tokens`, `tools_called`, `meta`.

## 2.5 Document Service
Префикс `/internal/documents`.
- `GET /internal/documents` — список.
- `GET /internal/documents/{doc_id}` — карточка.
- `GET /internal/documents/{doc_id}/sections/{section_id}` — секция.
- `POST /internal/documents/status` — обновление статуса ingestion.

## 2.6 Ingestion Service
Префикс `/internal/ingestion`.

### `POST /internal/ingestion/enqueue`
Принимает multipart с файлом и метаданными, возвращает `job_id`/`doc_id`/`status`.

### `POST /internal/ingestion/status`
Body: `{"job_id": "ing_456", "status": "processing", "error": null}`.

## 2.7 Асинхронные события
- Очередь `documents_to_ingest`: задания на обработку.
- Топик `document_ingested`: `doc_id`, `tenant_id`, `status`, количество секций/чанков.
- Топик `ingestion_failed`: `doc_id`, `error`, количество попыток.

---

# 3. Сводка
- `/api/v1/...` — публичные запросы от UI/интеграций.
- `/internal/...` — внутренние сервисы (Gateway ↔ Orchestrator ↔ Safety ↔ Retrieval ↔ LLM ↔ Ingestion ↔ Document Service).
- Асинхронная модель: ingestion публикует события для синхронизации статусов.
