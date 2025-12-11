# Technical Specification (TZ)
## Microservice: **MCP Tools Proxy**
### Project: Orion Soft Internal AI Assistant — *Visior*

---

# 1. Назначение сервиса

**MCP Tools Proxy** — это микросервис‑посредник между LLM Service (который поддерживает tool-calls / Model Context Protocol) и внутренними ресурсами системы:

- Documents API (PDF/pages/sections),
- Retrieval API (поиск по документам по прямому запросу LLM),
- Metadata DB,
- любые безопасные внутренние инструменты, доступные модели.

Задача MCP Tools Proxy — предоставить **ограниченный, безопасный, sandboxed** интерфейс для LLM‑модели, позволяющий ей:

- читать конкретные страницы документа,
- получать дополнительные сведения о документе,
- делать точечный поиск по документу,
- получать структурированные данные, недоступные в RAG контексте.

При этом модель **не имеет прямого доступа ни к хранилищу, ни к API**, а может использовать только безопасные инструменты, которые MCP Tools Proxy предоставляет.

---

# 0. Implementation Notes

- Скелет сервиса: `services/mcp_tools_proxy` (FastAPI).
- Публичные ручки: `/internal/mcp/execute`, `/health`.
- Инструменты оформлены как `BaseTool` классы (`tools/*.py`), обёрнуты в `ToolRegistry`, который также применяет лимиты по вызовам/токенам.
- Документы/метаданные берутся из mock-репозитория (`clients/documents.py`) до интеграции с реальными сториджами.
- Конфигурация через `MCP_PROXY_*` переменные (`config.py`): лимиты страниц, размер ответа, rate limits, блоклисты.
- Юнит‑тесты (`services/mcp_tools_proxy/tests`) покрывают успехи, изоляцию tenant, лимиты и список инструментов.

---

# 2. Область ответственности

## 2.1 Входит в ответственность

1. Реализация **MCP‑совместимых инструментов**:
   - `read_doc_section`
   - `read_doc_pages`
   - `read_doc_metadata`
   - `doc_local_search` (внутридокументный поиск)
   - `list_available_tools`
   - (опционально) бизнес‑специфичные инструменты

2. Контроль безопасности:
   - запрет на чтение чужих tenants,
   - лимиты по длине выдачи,
   - лимит частоты вызовов (tool-call rate limit),
   - выявление попыток вытащить слишком много контента (leakage prevention).

3. Взаимодействие с другими сервисами:
   - Metadata DB,
   - Document Store (S3/MinIO),
   - Ingestion Service (только чтение),
   - Retrieval (внутридокументный поиск).

4. Нормализация результатов для LLM:
   - trimming,
   - masking PII,
   - унифицированный JSON‑формат.

5. Строгая изоляция инструментов:
   - LLM никогда не может получить бинарный PDF,
   - не может скачивать файлы,
   - не имеет прямого доступа к БД.

## 2.2 Не входит в ответственность

- выполнение RAG поиска (это Retrieval Service),
- генерация ответов (LLM Service),
- safety-проверка (это Safety Service),
- ingestion документов.

---

# 3. Архитектура (High-level)

```text
LLM Service
   ↕ (MCP tool-calls)
MCP Tools Proxy
   ├─ Metadata DB
   ├─ Document Store (pages/text)
   ├─ Retrieval Service (local search)
   └─ Policy Rules (tenant isolation, security)
```

Сервис является stateless и легко масштабируется горизонтально.

---

# 4. Поддерживаемые инструменты MCP

## 4.1. Общий формат инструмента

Каждый MCP tool использует формат:

```json
{
  "name": "tool_name",
  "arguments": {
      ... input fields ...
  }
}
```

Ответ:

```json
{
  "status": "ok" | "error",
  "result": { ... },
  "error": null | {
     "code": "TOOL_ERROR",
     "message": "Explanation"
  }
}
```

---

# 5. Интерфейсы (Internal API для LLM Service)

## 5.1 `POST /internal/mcp/execute`

Выполняет один MCP tool-call.

### Request

```json
{
  "tool_name": "read_doc_section",
  "arguments": {
    "doc_id": "doc_123",
    "section_id": "sec_ldap"
  },
  "user": {
    "user_id": "u_1",
    "tenant_id": "tenant_1"
  },
  "trace_id": "abc-def-123"
}
```

### Response

```json
{
  "status": "ok",
  "result": {
    "text": "Полный текст секции ... (обрезанный по лимиту)",
    "page_start": 6,
    "page_end": 9,
    "tokens": 520
  },
  "trace_id": "abc-def-123"
}
```

Ошибка:

```json
{
  "status": "error",
  "error": {
    "code": "ACCESS_DENIED",
    "message": "User cannot access document doc_999"
  },
  "trace_id": "abc-def-123"
}
```

---

# 6. Описание инструментов

## 6.1 Tool: `read_doc_section`

### Аргументы:

- `doc_id`
- `section_id`

### Действия:

- проверить права tenant,
- извлечь секцию из Metadata DB,
- загрузить её текст из Document Store,
- выполнить token trimming (лимит ≈ 1–2k токенов),
- вернуть результат.

### Ответ:

```json
{
  "text": "Текст секции...",
  "page_start": 3,
  "page_end": 5,
  "tokens": 830
}
```

---

## 6.2 Tool: `read_doc_pages`

### Аргументы:

- `doc_id`
- `page_start`
- `page_end` (ограничивать ≤ 5 страниц за один вызов)

### Поведение:

- загрузить текст указанных страниц,
- выполнить очистку (remove headers/footers),
- лимитировать размер ответа.

---

## 6.3 Tool: `read_doc_metadata`

### Аргументы:

- `doc_id`

### Возвращает:

- заголовок,
- список секций,
- страницы,
- теги,
- версия продукта.

Используется LLM для ориентирования в документе.

---

## 6.4 Tool: `doc_local_search`

### Аргументы:

- `doc_id`,
- `query`,
- `max_results` (≤ 5)

### Поведение:

- поиск по тексту документа (BM25 или substring search),
- извлечение коротких фрагментов вокруг совпадений,
- выдача «ответных сниппетов».

---

## 6.5 Tool: `list_available_tools`

Возвращает JSON:

```json
{
  "tools": [
    "read_doc_section",
    "read_doc_pages",
    "read_doc_metadata",
    "doc_local_search"
  ]
}
```

LLM может использовать это для определения доступных возможностей.

---

# 7. Поток обработки MCP tool-call

```text
LLM → LLM Service → MCP Tools Proxy → internal resources → proxy → LLM Service → Orchestrator
```

Шаги:

1. LLM Service получает tool-call.
2. Делегирует вызов в MCP Tools Proxy.
3. MCP Tools Proxy:
   - валидирует права,
   - исполняет запрос,
   - применяет ограничения,
   - собирает нормализованный ответ.
4. Возврат результата в LLM Service.
5. LLM продолжает генерацию.

---

# 8. Ограничения и безопасность

## 8.1 Tenant isolation

Все инструменты должны проверять:

```
doc.tenant_id == user.tenant_id
```

Ошибка:

```json
{
  "status": "error",
  "code": "ACCESS_DENIED"
}
```

## 8.2 Rate limiting (anti-exfiltration)

Пример:

- не более 10 запросов на документ за одну генерацию,
- не более 20 KB текста возвращаемого контента,
- не более 5 страниц за один вызов.

Если превышено:

```
status: error
code: RATE_LIMIT_EXCEEDED
```

## 8.3 Sanitization

- удаление потенциально секретных вставок,
- маскирование токенов / PII (если есть вероятность утечки).

## 8.4 Logging & audit

В логи:

- tool_name,
- doc_id,
- tenant_id,
- количество возвращённых токенов,
- rate-limit state,
- trace_id.

**Не логировать** полный текст.

---

# 9. Нефункциональные требования

## 9.1 Производительность

Цель (p95):
- `read_doc_section` ≤ 50–80 ms,
- `read_doc_pages` ≤ 60–120 ms,
- `doc_local_search` ≤ 70–140 ms.

## 9.2 Масштабируемость

- Stateless, масштабирование горизонтальное,
- Document Store connection pooling,
- Metadata DB readonly режим.

## 9.3 Надёжность

- Retry = 1 для Document Store,
- Circuit breaker при недоступности S3/Minio,
- Fallback (если секция повреждена): возвращать error.

---

# 10. Конфигурация

## ENV переменные:

- `METADATA_DB_URL`
- `DOCUMENT_STORE_URL`
- `DOC_CHUNK_LIMIT_TOKENS`
- `MCP_RATE_LIMIT_CALLS`
- `MCP_RATE_LIMIT_TOKEN_OUTPUT`
- `LOG_LEVEL`

---

# 11. Тестирование

## 11.1 Unit Tests

- права доступа,
- корректность чтения секций,
- trimming,
- rate limiting,
- обработка ошибок.

## 11.2 Integration Tests

- взаимодействие с Document Store,
- поиск по документу,
- корректность работы при повреждённых данных.

## 11.3 Security Tests

- попытки чтения чужих tenants,
- попытки чтения всего документа через page-iteration,
- тесты exfiltration resistance.

---

# 12. Открытые вопросы

1. Нужно ли поддерживать streaming результатов?
2. Должны ли инструменты позволять LLM читать изображения/таблицы?
3. Нужен ли инструмент "semantic search inside doc" через embeddings, или достаточно BM25?
4. Следует ли LLM иметь tool для вызова Retrieval Service напрямую?

---

# END OF DOCUMENT
