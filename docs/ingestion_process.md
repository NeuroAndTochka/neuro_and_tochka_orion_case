# Процесс Ingestion (Visior)

Обновлённое описание пайплайна `ingestion_service` (ветка `main`). Сервис запускается в `mock_mode` по умолчанию, поэтому все внешние зависимости опциональны.

## Цели
- Принять файл от API Gateway/Observer, сохранить его и сформировать секции/чанки.
- Сгенерировать эмбеддинги и краткие summary секций.
- Обновить Document Service и (опционально) Chroma vector store.
- Работать в локальном режиме без внешних ключей/DSN.

## Архитектура
```
Gateway → /internal/ingestion/enqueue
    ↳ StorageClient (S3/local)
    ↳ JobStore + очередь (in-memory или Redis)
    ↳ EmbeddingClient (OpenAI-style или mock)
    ↳ Summarizer (OpenAI-style или fallback)
    ↳ VectorStore (Chroma, отключён в mock_mode)
    ↳ process_file (фоновая задача/worker)
```

## Конфигурация (`INGEST_*`)
- Режимы: `MOCK_MODE` (true по умолчанию) — локальный storage, псевдо-эмбеддинги, Chroma отключена.
- Storage: `S3_*` (endpoint/bucket/access/secret/region/secure), `LOCAL_STORAGE_PATH`, `STORAGE_PATH`.
- Document Service: `DOC_SERVICE_BASE_URL` — включает регистрацию секций/статуса.
- Очередь/JobStore: `REDIS_URL`, `WORKER_COUNT`, `QUEUE_NAME`, `MAX_ATTEMPTS`, `RETRY_DELAY_SECONDS`.
- Embeddings: `EMBEDDING_API_BASE/KEY/MODEL`, `EMBEDDING_MAX_ATTEMPTS`, `EMBEDDING_RETRY_DELAY_SECONDS`.
- Summarizer: `SUMMARY_API_BASE/KEY/MODEL/REFERER/TITLE`.
- Ограничения: `MAX_PAGES`, `MAX_FILE_MB`, `CHUNK_SIZE`, `CHUNK_OVERLAP`.
- Vector store: `CHROMA_PATH`, `CHROMA_HOST` (используется, если `mock_mode=false`).

## Публичные API (все требуют `X-Tenant-ID`)
- `POST /internal/ingestion/enqueue` — multipart `file`, опц. `product/version/tags`; выдаёт `job_id`, `doc_id`, `status`, `storage_uri`.
- `POST /internal/ingestion/status` — обновление статуса job; при наличии Document Service проксирует статус туда.
- `GET /internal/ingestion/jobs/{job_id}` — состояние и логи.
- `GET/POST /internal/ingestion/summarizer/config` — system prompt/model/use_roles.
- `GET/POST /internal/ingestion/chunking/config` — `chunk_size`, `chunk_overlap`.
- `GET /internal/ingestion/documents/{doc_id}/tree` — дерево документа + чанки из vector store (если включён) и Document Service.

## Pipeline `process_file`
1. Скачивание байтов и временная запись файла (если нужно) через `StorageClient`.
2. Парсинг `DocumentParser` (PDF/DOCX/текст) с ограничениями по страницам/размеру; базовый чистый текст, если формат неизвестен.
3. Формирование секций/чанков по страницам, summary секций (обрезка либо вызов Summarizer).
4. Эмбеддинги документа/секций/чанков через OpenAI-совместимый endpoint или псевдо-эмбеддинги в mock режиме; логи пишутся в JobStore.
5. Upsert секций и статуса в Document Service (если URL задан).
6. Upsert doc/section/chunk в Chroma при включённом vector store.
7. Обновление job → `indexed` или `failed` и публикация события в JobStore (Redis stream при наличии).

## Ограничения и известные пробелы
- Очередь/воркеры ненадёжные (in-memory или Redis list), нет подтверждений доставки.
- Ошибки внешних вызовов (Document Service, S3, Chroma) логируются, но ретраи ограничены количеством попыток job.
- Нет отдельной проверки прав доступа кроме `X-Tenant-ID`.

## Быстрый старт
```bash
# mock режим
cd services/ingestion_service
export INGEST_MOCK_MODE=true
pip install -e '.[dev]'
uvicorn ingestion_service.main:app --reload --port 8050
```
Или поднять весь стек: `docker compose up --build`.
