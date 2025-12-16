# Техническая спецификация — Ingestion Service

## 1. Назначение
Принимать документы от Gateway/Observer, сохранять их в хранилище, запускать пайплайн парсинга → секции/чанки → эмбеддинги/summary, обновлять Document Service и Chroma (если включено). Очередь и JobStore могут жить в памяти или Redis.

## 2. API (`/internal/ingestion`)
- `POST /enqueue` — multipart `file`, опц. `product/version/tags`, заголовок `X-Tenant-ID`. Ответ: `job_id`, `doc_id`, `tenant_id`, `status`, `storage_uri`.
- `POST /status` — обновление статуса job (`job_id`, `status`, `error?`). Если настроен Document Service, также отправляет статус туда.
- `GET /jobs/{job_id}` — статус и логи.
- `GET/POST /summarizer/config` — модель/prompt/use_roles.
- `GET/POST /chunking/config` — `chunk_size`, `chunk_overlap`.
- `GET /documents/{doc_id}/tree` — объединённая информация из Document Service + метаданные чанков из Chroma (если включён vector_store).
- `/health` — `{"status":"ok"}`.

## 3. Пайплайн
1. Сохранение файла через `StorageClient` (S3 или локальная папка). Генерация `doc_id`/`job_id`.
2. Парсинг файла `DocumentParser` (PDF/DOCX/текст), ограничение по `max_pages` и `max_file_mb`.
3. Разбиение текста на секции/чанки по страницам (`chunk_size`, `chunk_overlap`).
4. Embedding (OpenAI-style endpoint или псевдо-эмбеддинги в mock режиме) для документа/секций/чанков; логирование вызовов в JobStore.
5. Summarizer (OpenAI-style endpoint или fallback на обрезку текста) для секций, тоже логируется.
6. Upsert секций + статуса в Document Service (если задан `doc_service_base_url`).
7. Upsert doc/section/chunk в Chroma через VectorStore, если не mock и установлен chromadb.
8. Обновление статуса job и публикация события в JobStore.

## 4. Конфигурация (`INGEST_*`)
`mock_mode`, `storage_path`, `local_storage_path`, S3 настройки, `doc_service_base_url`, `redis_url`, `worker_count`, `queue_name`, `max_attempts`, `retry_delay_seconds`, `embedding_api_base/key/model`, `embedding_max_attempts`, `embedding_retry_delay_seconds`, `summary_api_base/key/model/referer/title`, `max_pages`, `max_file_mb`, `chunk_size`, `chunk_overlap`, `chroma_path/host`.

## 5. Ограничения
- Worker/queue — простые фоновые задачи; нет гарантированной доставки.
- Обработка ошибок в сетевых вызовах Document/Chroma минимальна (логирование + ретрай по количеству попыток job).
- Security: rely on `X-Tenant-ID`; дополнительные проверки прав отсутствуют.

## 6. Тестирование
Юнит и интеграционные тесты в `services/ingestion_service/tests` покрывают JobStore, очередь и базовый пайплайн в mock режиме. Для продового стека нужны тесты с MinIO/Chroma.
