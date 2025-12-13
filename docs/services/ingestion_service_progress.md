# Ingestion Service — progress

## Что уже реализовано
- Эндпоинты `/internal/ingestion/enqueue` и `/internal/ingestion/status` + `/health` на FastAPI (`routers/ingestion.py`, `main.py`); `enqueue` требует `X-Tenant-ID` и multipart файл, возвращает `job_id/doc_id/status/storage_uri`.
- In-memory/Redis JobStore с логами и событиями, очередь IngestionQueue (Redis или asyncio.Queue), configurable worker_count.
- Пайплайн обработки (`core/pipeline.process_file`): скачивание из storage, парсинг страниц, чанкинг, embedding (doc/sections/chunks), summarizer, upsert секций/статуса в Document Service, запись в vector store (интерфейс), логирование шагов в JobStore.
- StorageClient (s3/local) для upload/download; DocumentParser с max_pages/max_file_mb; EmbeddingClient/Summarizer mock реализации; vector store интерфейс (Chroma путь/host в конфиге).
- Конфигурация через `INGEST_*` (`config.py`): storage/S3, doc_service_base_url, Redis URL/queue name, worker_count, лимиты по страницам/файлу/чанку, embedding/summary endpoints/модели, retry параметры, mock_mode.
- Тесты: unit/integration на enqueue/status и пайплайн через background queue (`services/ingestion_service/tests/test_ingestion.py`).

## Как это реализовано
- `main.py` создаёт StorageClient, JobStore, IngestionQueue, EmbeddingClient, Summarizer, VectorStore и сохраняет в app.state; при mock_mode storage переключается на `local_storage_path` fallback.
- `enqueue`: создаёт doc_id/job_id, сохраняет JobRecord, опционально регистрирует документ в Document Service (без ошибок при сбое), ставит WorkItem в очередь или запускает background task `process_file`.
- `process_file`: читает файл, парсит страницы (PyPDF2/docx), строит секции/чанки (`_split_chunks`), делает embed/summary (пишет логи и payload в JobStore), upsert'ит секции/статус в Document Service (HTTP), пишет в vector store. При успехе статус `indexed`, публикует событие `document_ingested`; при ошибке — `failed`.
- JobStore хранит записи в Redis hash или памяти, публикует события в stream (если Redis), пишет логи в Redis list или память (хвост max_logs).
- Rate limiting/аудит отсутствуют; проверка tenant — только на уровне заголовка в `enqueue`.

## Что осталось сделать / отклонения от ТЗ
- Нет REST ручек для чтения job состояния/логов (`GET /internal/ingestion/jobs/{job_id}`) и конфигов summarizer, document tree — описаны в ТЗ, но не реализованы.
- Mock mode не отключает vector store/внешние вызовы явно; embedding/summarizer используют простые локальные функции, но нет явных mock ответов/логики для Chroma.
- Нет брокера/воркеров вне процесса (SQS/Kafka/отдельные воркеры), retries/`max_attempts`/`retry_delay_seconds` не применяются в pipeline/очереди.
- Валидация входных данных ограничена: нет лимитов на размер файла/страниц на уровне API, нет проверки tags/product/version, не логируются X-Request-ID.
- Безопасность/изоляция: нет аутентификации/service token, tenant проверяется только в заголовке; status endpoint не требует tenant, может обновлять любой job.
- Наблюдаемость: нет метрик/трассировки для стадий пайплайна, нет экспорта событий в шину кроме Redis stream; ошибки Document Service игнорируются без retry.
