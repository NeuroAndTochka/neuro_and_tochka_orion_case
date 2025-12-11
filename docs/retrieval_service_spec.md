# Technical Specification (TZ)
## Microservice: **Retrieval Service**
### Project: Orion Soft Internal AI Assistant — *Visior*

---

# 1. Назначение сервиса

**Retrieval Service** отвечает за многоступенчатый поиск релевантной информации в корпоративных документах.
Он обеспечивает:

- document-level retrieval,
- section-level retrieval (основная точка входа),
- chunk-level retrieval (точный поиск),
- объединение dense + sparse поиска (hybrid search),
- reranking,
- сбор оптимального набора чанков для контекста LLM,
- token-aware context building.

Сервис максимально изолирован:
независим от LLM, не знает о Safety, не анализирует смысл запроса — только осуществляет поиск.

---

# 2. Scope / Зона ответственности

## 2.1 Входит в ответственность

1. **Приём внутренних запросов на поиск контекста.**
2. **Трансформация поискового запроса** (опциональный query rewriting).
3. **Выполнение поиска:**
   - поиск по doc embeddings,
   - поиск по section embeddings,
   - chunk embeddings,
   - sparse BM25 / keyword matching.
4. **Ранжирование результатов:**
   - score normalization,
   - hybrid scoring (dense + sparse),
   - reranking (cross-encoder, ML-ранкер, rule-based).
5. **Формирование итогового списка чанков:**
   - учёт token-limit,
   - разнообразие документов,
   - приоритет релевантных секций,
   - удаление дубликатов,
   - предоставление MCP-ссылок на оригинальные страницы документа.
6. **Возврат структурированного результата для AI Orchestrator.**

## 2.2 Не входит в ответственность

Retrieval Service **не**:

- вызывает LLM,
- выполняет safety-проверки,
- управляет ingestion документов (получает готовые индексы),
- выполняет MCP-функции — только предоставляет ссылки для LLM Service,
- формирует конечный ответ пользователю.

---

# 3. Архитектура на высоком уровне

```text
AI Orchestrator
   ↓
Retrieval Service
   ├─ Vector DB (doc_index, section_index, chunk_index)
   ├─ Metadata DB (documents, sections, schema)
   └─ Optional ML Reranker
```

Сервис stateless, оптимизирован под высокую нагрузку на поиск.

---

# 4. Внешние интерфейсы (Internal API)

## 4.1 Основной эндпоинт

### `POST /internal/retrieval/search`

#### Request

```json
{
  "tenant_id": "tenant_1",
  "query": "Как настроить LDAP интеграцию в Orion X?",
  "language": "ru",
  "params": {
    "max_docs": 20,
    "max_sections": 50,
    "max_chunks": 40,
    "context_token_limit": 4096,
    "retrieval_mode": "section_first",
    "enable_hybrid": true,
    "enable_rerank": true
  },
  "trace_id": "abc-def-123"
}
```

Описание полей:

- `retrieval_mode` может быть:
  - `"doc_first"` — сначала doc embeddings,
  - `"section_first"` — основной путь,
  - `"chunk_priority"` — максимальная точность,
  - `"hybrid_only"` — только dense + sparse.
- `context_token_limit` — лимит для итогового набора чанков.
- `enable_rerank` — включает финальный ML reranking.

#### Response

```json
{
  "chunks": [
    {
      "chunk_id": "ch_2001",
      "doc_id": "doc_123",
      "section_id": "sec_ldap",
      "text": "Для настройки LDAP интеграции в Orion X...",
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
  "used_sections": [
    {
      "section_id": "sec_ldap",
      "score": 0.91
    }
  ],
  "meta": {
    "retrieval_time_ms": 130,
    "mode": "section_first",
    "hybrid_used": true,
    "rerank_used": true,
    "trace_id": "abc-def-123"
  }
}
```

---

# 5. Многоступенчатый поиск (Core Logic)

## 5.1 Шаг 1. Query Normalization

Включает:

- нормализацию (строчные буквы, удаление лишних символов),
- определение языка,
- (опционально) query expansion:

```text
"LDAP integration Orion X" → ["LDAP", "Active Directory", "authentication", ...]
```

Используется только если включено `enable_hybrid`.

---

## 5.2 Шаг 2. Document-level Retrieval

1. Поиск по `doc_index` embeddings.
2. Фильтр по tenant_id.
3. Top-K документов (`max_docs`).
4. Score normalization.

---

## 5.3 Шаг 3. Section-level Retrieval

Для документов из шага 2:

1. dense search по summary embeddings,
2. sparse search (BM25) по тексту секций,
3. hybrid scoring:

```
score = 0.7*dense + 0.3*sparse
```

4. top-K секций (`max_sections`).

---

## 5.4 Шаг 4. Chunk-level Retrieval

Для каждой секции берутся chunk embeddings.

Шаги:

- dense search,
- sparse search,
- hybrid score,
- удаление дубликатов,
- нормализация,
- отбор top-N (`max_chunks`).

---

## 5.5 Шаг 5. Reranking (опционально)

Если `enable_rerank = true`, используется cross-encoder:

Input:

```
(query, chunk_text)
```

Output:

```
confidence_score ∈ [0..1]
```

После reranking:

- сортировка чанков,
- агрегация по документам,
- перезапись итогового score.

---

## 5.6 Шаг 6. Token-aware Context Builder

Правила:

1. Выбирать чанки из разных документов.
2. Сохранять порядок секций (если chunk span последовательный).
3. Умещать всё в token_limit.
4. Если чанки превышают лимит —:
   - исключать самые низкие по score,
   - или объединять соседние чанки (если суммарно меньше лимита),
   - или укорачивать текст чанков (если включён hard-trim режим).

---

# 6. Данные и Индексы

## 6.1 Vector DB

Содержит три независимых индекса:

### `doc_index`
- doc_id
- embedding
- product/version
- tenant_id

### `section_index`
- section_id
- doc_id
- summary
- summary_embedding
- page ranges

### `chunk_index`
- chunk_id
- doc_id
- section_id
- text
- tokens
- page_start / page_end
- chunk_embedding

Vector DB: **Qdrant**, **Weaviate**, **Pinecone**, **Milvus** — любой поддерживающий фильтры и payload.

---

## 6.2 Metadata DB

Таблицы:

- `documents`
- `sections`
- `chunks`
- `products`
- `versions`

Используется PostgreSQL.

---

# 7. Нефункциональные требования

## 7.1 Производительность

- response time ≤ **50–120 ms** (p95) без rerank,
- ≤ **150–300 ms** с rerank,
- TPS: ≥ 500 RPS при горизонтальном масштабировании.

## 7.2 Надёжность

- circuit breakers к Vector DB,
- retry count ≤ 2,
- fallback: вернуть пустой список чанков (Orchestrator сам решит fallback-путь).

## 7.3 Масштабируемость

- Stateless: горизонтальное масштабирование.
- Кэширование:
  - query → results (опционально),
  - embeddings в RAM.

## 7.4 Observability

Метрики:

- `retrieval_requests_total`,
- `retrieval_latency_ms`,
- `retrieval_mode_count{mode}`,
- `retrieval_hybrid_usage_total`,
- `retrieval_rerank_usage_total`,
- `retrieval_empty_results_total`.

Логи:

- trace_id,
- doc/section/chunk candidates count,
- ошибки индексации,
- медленные запросы.

---

# 8. Конфигурация

## 8.1 Environment Variables

- `VECTOR_DB_URL`
- `METADATA_DB_URL`
- `DEFAULT_MAX_DOCS`
- `DEFAULT_MAX_SECTIONS`
- `DEFAULT_MAX_CHUNKS`
- `DEFAULT_TOKEN_LIMIT`
- `ENABLE_HYBRID`
- `ENABLE_RERANK`
- `RERANK_MODEL_URL`
- `LOG_LEVEL`

---

# 9. Тестирование

## 9.1 Unit tests

- hybrid scoring,
- correct token counting,
- deduplication,
- normalization and filtering.

## 9.2 Integration tests

- работа с Qdrant/Weaviate,
- нагрузочное тестирование (latency under load),
- полные сценарии document→section→chunk.

## 9.3 Relevance Testing

A/B сравнение:

- RAG комплект чанков vs baseline,
- reranking enable/disable,
- hybrid enable/disable.

---

# 10. Открытые вопросы

1. Должен ли сервис выполнять query rewriting с помощью LLM?
2. Нужно ли делать обратный поиск (reverse lookup) — например, по product/version?
3. Какой лимит на размер chunk должен быть использован по умолчанию?
4. Должен ли сервис поддерживать streaming выдачу чанков?

---

# END OF DOCUMENT
