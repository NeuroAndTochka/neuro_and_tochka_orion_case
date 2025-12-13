# Ingestion Service

## Назначение
Ingestion Service принимает файлы от API Gateway, кладёт их в хранилище, запускает пайплайн парсинга/эмбеддингов/саммари и обновляет статусы в Document Service. Сервис — буфер между загрузкой и индексацией.

## Архитектура
- FastAPI (`services/ingestion_service`).
- StorageClient: S3/MinIO или `local://`/файловая система (mock).
- JobStore: in-memory или Redis (если указан `INGEST_REDIS_URL`); очередь ingest‑job'ов на Redis или in-memory fallback, воркеры внутри сервиса.
- Pipeline: парсинг страниц → chunking → embeddings (doc/section/chunk) → LLM-саммари секций → запись секций/статуса в Document Service → опциональный Chroma vector store.
- Summarizer/Embedding: OpenAI-совместимые endpoint'ы либо mock фоллбеки.

## Конфигурация
| Переменная | Описание |
| --- | --- |
| `INGEST_MOCK_MODE` | `true` по умолчанию; включает локальный storage, псевдо-эмбеддинги, отключает Chroma. |
| `INGEST_S3_*` | `ENDPOINT`, `BUCKET`, `ACCESS_KEY`, `SECRET_KEY`, `REGION`, `SECURE` — включают S3/MinIO. |
| `INGEST_LOCAL_STORAGE_PATH` / `INGEST_STORAGE_PATH` | Каталог для `local://` и файлового fallback. |
| `INGEST_DOC_SERVICE_BASE_URL` | URL Document Service для upsert секций/статусов. |
| `INGEST_REDIS_URL` | Включает Redis-backed JobStore; без него хранилище волатильно. |
| `INGEST_WORKER_COUNT` | Количество воркеров очереди (по умолчанию 1). |
| `INGEST_QUEUE_NAME` | Имя очереди в Redis (по умолчанию `ingestion_queue`). |
| `INGEST_MAX_ATTEMPTS`, `INGEST_RETRY_DELAY_SECONDS` | Ретраи пайплайна при ошибках. |
| `INGEST_EMBEDDING_API_BASE`, `INGEST_EMBEDDING_API_KEY`, `INGEST_EMBEDDING_MODEL` | Настройки эмбеддингов. |
| `INGEST_SUMMARY_API_BASE`, `INGEST_SUMMARY_API_KEY`, `INGEST_SUMMARY_MODEL` | Настройки summarizer'а. |
| `INGEST_MAX_PAGES`, `INGEST_MAX_FILE_MB`, `INGEST_CHUNK_SIZE`, `INGEST_CHUNK_OVERLAP` | Лимиты парсинга/чанков. |
| `INGEST_CHROMA_PATH` | Путь для Chroma vector store (работает при `mock_mode=false`). |

## API
Все запросы требуют заголовок `X-Tenant-ID`.

### `POST /internal/ingestion/enqueue`
Multipart `file` (+ optional `product|version|tags`). Возвращает `job_id`, `doc_id`, `status`, `storage_uri`; запускает фоновой pipeline.

```bash
curl -H "X-Tenant-ID: tenant_1" -F "file=@spec.pdf" -F "product=IAM" \
  http://ingest.local/internal/ingestion/enqueue
```

### `POST /internal/ingestion/status`
Обновляет статус job, пушит статус в Document Service (если настроен). Тело: `job_id`, `status`, `error?`.

### `GET /internal/ingestion/jobs/{job_id}`
Возвращает состояние job и последние логи (embedding/summary вызовы, payload'ы).

### `GET/POST /internal/ingestion/summarizer/config`
Чтение/обновление конфига summarizer (prompt, model, max_tokens, use_roles).

### `GET /internal/ingestion/documents/{doc_id}/tree`
Дерево секций документа из Document Service + чанки из Chroma (если включён vector store).

## Расширение
- Подключить реальный брокер/воркеры вместо background tasks (SQS/Kafka/Redis Queue) и добавить ретраи S3/LLM.
- Уточнить парсинг (DOCX/PDF), overlap chunking и rerank.
- Документировать новые статусы/события ingestion и прокинуть в Document Service/шину.

## Mock требования
- `mock_mode=true` включает псевдо-эмбеддинги, локальное хранилище и отключает vector store.
- Добавляя поля в ответы (`EnqueueResponse`, логи), обновляйте mock и тесты (`services/ingestion_service/tests`).
