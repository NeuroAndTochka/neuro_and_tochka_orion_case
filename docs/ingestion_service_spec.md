# Technical Specification (TZ)  
## Microservice: **Ingestion Service**  
### Project: Orion Soft Internal AI Assistant — *Visior*

---

# 1. Назначение сервиса

**Ingestion Service** — это микросервис, отвечающий за полную обработку документов, загруженных пользователями, включая:

- приём задания на обработку (через очередь),
- безопасное скачивание PDF/DOCX из хранилища,
- парсинг текста и структуры документа,
- определение секций, заголовков, подзаголовков,
- извлечение страниц, таблиц, изображений (опционально),
- разбиение текста на чанки для RAG (chunking),
- генерацию summary для секций,
- генерацию embeddings для:
  - документа,
  - секций,
  - чанков,
- запись индексов в Vector DB,
- обновление статуса документа в Metadata DB,
- отправку событий (indexed / failed).

Этот сервис является фундаментом для корректной работы Retrieval Service и RAG.

---

# 2. Scope / Зона ответственности

## 2.1 Входит в ответственность

1. Получение задания через очередь `documents_to_ingest`.  
2. Загрузка документа из объектного хранилища (S3/MinIO).  
3. Парсинг:
   - извлечение текста постранично,
   - извлечение структуры,
   - извлечение метаданных.  
4. Разбиение:
   - выделение секций,
   - chunking (с учётом токенов моделей),
   - нормализация контента.  
5. Summarization:
   - генерация LLM-сводок для секций (или ML-модели).  
6. Embeddings:
   - document embedding,
   - section summary embeddings,
   - chunk embeddings.  
7. Запись результатов:
   - Vector DB: doc_index, section_index, chunk_index,
   - Metadata DB: documents, sections, chunks.  
8. Отправка событий:
   - `document_ingested`,
   - `ingestion_failed`.  
9. Логирование и аудит.

## 2.2 Не входит в ответственность

- приём файла от пользователя (это делает Gateway),  
- RAG-поиск (Retrieval Service),  
- safety анализ,  
- взаимодействие с LLM в режиме ответа на вопросы (это LLM Service),  
- управление tenant’ами.

---

# 3. Архитектура (High-Level)

```text
API Gateway → documents_to_ingest (queue)
                         ↓
               Ingestion Service (workers)
                         ↓
                 Document Store (S3/MinIO)
                         ↓
         Text Parser / Structure Extractor
                         ↓
          Sectionizer → Chunker → Summarizer
                         ↓
             Embeddings Generator (LLM/encoder)
                         ↓
     Vector DB (doc_index, section_index, chunk_index)
                         ↓
             Metadata DB (PostgreSQL)
                         ↓
         document_ingested / ingestion_failed events
```

Сервис исполняется в нескольких воркерах (Celery/Dramatiq/RQ), поддерживает параллельность.

---

# 4. External Interfaces

## 4.1 Очередь входящих задач

### Queue: `documents_to_ingest`

Сообщение:

```json
{
  "job_id": "ing_456",
  "doc_id": "doc_123",
  "tenant_id": "tenant_1",
  "file_path": "s3://bucket/orion/doc_123.pdf",
  "product": "Orion X",
  "version": "1.2",
  "tags": ["admin", "ldap"],
  "created_at": "2025-12-04T10:00:00Z"
}
```

---

## 4.2 Событие успеха

### Topic: `document_ingested`

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

## 4.3 Событие провала

### Topic: `ingestion_failed`

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

# 5. Pipeline (Detailed)

## 5.1 Step 1 — Fetch Document

1. Получить файл из S3/MinIO.  
2. Проверить MIME type.  
3. Проверить лимиты:
   - максимальный размер файла (напр. 50–100 MB),
   - максимальное количество страниц (напр. 2000).  
4. Записать `status = processing` в Metadata DB.

---

## 5.2 Step 2 — Parse Document

Поддерживаемые форматы:

- PDF (основной),
- DOCX (вторично),
- Markdown (необязательно).

Парсер должен извлечь:

- текст постранично,
- структуру заголовков (если есть),
- таблицы и изображения (опционально),
- размер в токенах.

Используемые либы:

- **PDFMiner**, **PyMuPDF**, или **Unstructured.io**.

Вывод парсера:

```json
{
  "pages": [
    { "page": 1, "text": "..." },
    { "page": 2, "text": "..." }
  ],
  "metadata": {
    "title": "...",
    "author": "...",
    "pages": 120
  }
}
```

---

## 5.3 Step 3 — Sectionizer

Цель: определить логическую структуру документа.

Методы:

- анализ заголовков (regex: `^\d+(\.\d+)*\s+Title`),  
- модель BERT-confidence (опционально),  
- эвристики (порог расстояний между заголовками).  

Каждая секция:

```json
{
  "section_id": "sec_ldap",
  "doc_id": "doc_123",
  "title": "LDAP Configuration",
  "page_start": 6,
  "page_end": 12,
  "text": "полный текст секции"
}
```

---

## 5.4 Step 4 — Chunking

Chunking — важнейший этап RAG.

Принципы:

- чанк ≈ 300–500 токенов,  
- разбиение по смысловым параграфам,  
- если параграф слишком большой → делить,  
- если несколько маленьких — объединять до размера.  

Пример чанка:

```json
{
  "chunk_id": "ch_2001",
  "section_id": "sec_ldap",
  "doc_id": "doc_123",
  "text": "To configure LDAP integration...",
  "tokens": 340,
  "page_start": 6,
  "page_end": 7
}
```

---

## 5.5 Step 5 — Summarization (LLM)

Для каждой секции генерируется summary:

Вызов LLM Service:

```json
{
  "mode": "summary",
  "text": "полный текст секции",
  "max_tokens": 256
}
```

Вывод:

```json
"summary": "Этот раздел описывает настройку LDAP интеграции..."
```

---

## 5.6 Step 6 — Embeddings

Три уровня:

### 1. Document embedding
Вход:
```
summary(title + first N pages)
```

### 2. Section embedding
Вход:
```
section summary
```

### 3. Chunk embedding
Вход:  
```
chunk.text
```

Эмбеддер — локальный (например `bge-large`, `jina-embeddings`).

---

## 5.7 Step 7 — Indexing

### Vector DB

Коллекции:

- `doc_index`
- `section_index`
- `chunk_index`

Пример записи чанка:

```json
{
  "id": "ch_2001",
  "vector": [...],
  "payload": {
    "doc_id": "doc_123",
    "section_id": "sec_ldap",
    "tokens": 340,
    "page_start": 6,
    "page_end": 7
  }
}
```

### Metadata DB

Таблицы:

- `documents` → статус, метаданные,
- `sections` → секции,
- `chunks` → чанки.

После успешной индексации:

`status = indexed`.

---

# 6. Нефункциональные требования

## 6.1 Производительность

Цель: один документ ≤ **3–10 секунд** (в зависимости от размера).  
Параллельность: ≥ 20 воркеров.

## 6.2 Надёжность

- retry при падении S3/parsers,  
- дедубликация задач по job_id,  
- partial rollback при неуспехе.

## 6.3 Observability

Метрики:

- `ingestion_jobs_total`,
- `ingestion_latency_ms`,
- `ingestion_chunks_total`,
- `ingestion_failures_total`.

Логи:

- этапы пайплайна,
- время обработки,
- ошибки,
- trace_id.

---

# 7. Конфигурация

## ENV

- `DOCUMENT_STORE_URL`
- `VECTOR_DB_URL`
- `METADATA_DB_URL`
- `LLM_SERVICE_URL`
- `MAX_SECTION_SIZE_TOKENS`
- `CHUNK_SIZE_TOKENS`
- `MAX_FILE_SIZE_MB`
- `MAX_PAGES`
- `LOG_LEVEL`
- `WORKERS`

---

# 8. Тестирование

## Unit tests:

- парсер,
- sectionizer,
- chunker,
- summarizer mock,
- embeddings mock.

## Integration tests:

- полный ingestion (mock LLM),
- взаимодействие с Vector DB и Metadata DB.

## Stress tests:

- ingestion 100 документов подряд,
- искажение PDF, пустые страницы, шифрованные PDF.

---

# 9. Открытые вопросы

1. Нужна ли поддержка таблиц и изображений?  
2. Нужно ли сохранять оригинальную структуру PDF (layout-based retrieval)?  
3. Использовать ли GPU для summarization/embeddings?  
4. Поддерживать ли обновление существующего документа (incremental ingestion)?  

---

# END OF DOCUMENT
