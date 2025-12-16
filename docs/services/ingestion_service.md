# Ingestion Service

## Назначение
Принимает загрузки документов, сохраняет их в хранилище, запускает пайплайн парсинга/чанкования/эмбеддингов/summary, обновляет Document Service и, если включено, векторное хранилище (Chroma). Очередь и JobStore могут работать in-memory или на Redis.

## Эндпоинты (`/internal/ingestion`)
- `POST /enqueue` — multipart `file`, опц. `product/version/tags`, заголовок `X-Tenant-ID`. Возвращает `job_id`, `doc_id`, `status`, `storage_uri`.
- `POST /status` — обновление статуса job (`job_id`, `status`, `error?`).
- `GET /jobs/{job_id}` — статус и последние логи.
- `GET/POST /summarizer/config` — конфиг system prompt/model/use_roles для summarizer.
- `GET/POST /chunking/config` — `chunk_size`, `chunk_overlap` настройки.
- `GET /documents/{doc_id}/tree` — дерево секций + чанки из vector store и Document Service (нужен `doc_service_base_url`).
- `/health` — `{"status":"ok"}`.

## Пайплайн `process_file`
1. Скачивает файл из storage (S3/локальный path) и парсит страницы `DocumentParser` (ограничения `max_pages`, `max_file_mb`).
2. Делит текст на секции/чанки по страницам (`chunk_size`, `chunk_overlap`).
3. Строит embeddings (OpenAI-style или mock) для документа/секций/чанков; пишет логи в JobStore.
4. Строит summary секций через `Summarizer` (OpenAI-style или fallback на обрезку текста).
5. Upsert секций + статус в Document Service, если указан `doc_service_base_url`.
6. Upsert в Chroma (doc/section/chunk) через `VectorStore`, если не `mock_mode`.
7. Обновляет job статус и публикует событие в JobStore (Redis stream при наличии).

## Конфигурация (`INGEST_*`)
`mock_mode`, `storage_path`, S3 (`s3_endpoint/bucket/access_key/secret_key/region/secure`), `local_storage_path`, `doc_service_base_url`, `redis_url`, `worker_count`, `queue_name`, `max_attempts`, `retry_delay_seconds`, `embedding_api_base/key/model`, `embedding_max_attempts`, `embedding_retry_delay_seconds`, `summary_api_base/key/model/referer/title`, `max_pages`, `max_file_mb`, `chunk_size`, `chunk_overlap`, `chroma_path/host`.

## Особенности
- При `worker_count>0` запускает фоновые задачи, иначе фоновые задачи добавляются через `BackgroundTasks` при enqueue.
- `mock_mode=true` отключает Chroma и использует локальное хранилище, псевдо-эмбеддинги и fallback summary.
