# Процесс Ingestion (Visior)

Документ описывает текущий (v1) процесс ingestion в сервисе `ingestion_service` и связанные взаимодействия с остальными компонентами. Цель — зафиксировать продовый поток, конфигурацию и точки расширения.

## Цели
- Принимать файлы от API Gateway (через его прокси).
- Сохранять исходник в объектное хранилище (MinIO/S3).
- Регистрировать документ в Document Service.
- Обрабатывать содержимое: чанкинг, 3-уровневые эмбеддинги (doc/section/chunk).
- Обновлять метаданные/статусы в Document Service.
- Оставлять фоллбек для локальной разработки (mock mode, локальный storage, псевдо-эмбеддинги).

## Архитектура (текущая)
```
API Gateway → ingestion_service (/internal/ingestion/enqueue)
                 ├─ StorageClient (MinIO/S3 или local://)
                 ├─ JobStore (in-memory, планируется брокер)
                 ├─ EmbeddingClient (OpenAI-совместимый API или mock)
                 └─ Background task: pipeline.process_file
                        ├─ download_bytes
                        ├─ split → chunks → sections
                        ├─ embeddings: doc / section / chunk
                        └─ push sections + status → Document Service
```

## Конфигурация (важные переменные `INGEST_*`)
- `INGEST_MOCK_MODE` — `true` для локалки; включает локальный storage и псевдо-эмбеддинги.
- Хранилище:
  - `INGEST_S3_ENDPOINT`, `INGEST_S3_BUCKET`, `INGEST_S3_ACCESS_KEY`, `INGEST_S3_SECRET_KEY`, `INGEST_S3_REGION`, `INGEST_S3_SECURE`
  - `INGEST_LOCAL_STORAGE_PATH` — путь для `local://` в mock-режиме.
- Document Service:
  - `INGEST_DOC_SERVICE_BASE_URL` — URL (`http://document_service:8060` в docker-compose). Если задан, ingestion регистрирует документ и обновляет статус/секции.
- Эмбеддинги (OpenAI-style):
  - `INGEST_EMBEDDING_API_BASE` — базовый URL (например, `https://api.openai.com` или локальный runtime).
  - `INGEST_EMBEDDING_API_KEY` — ключ для Authorization Bearer.
  - `INGEST_EMBEDDING_MODEL` — модель (по умолчанию `text-embedding-3-small`).

## Публичные API
### POST `/internal/ingestion/enqueue`
Форма с полем `file` (UploadFile). Необязательные поля: `product`, `version`, `tags` (comma-separated).
Ответ:
```json
{
  "job_id": "job_xxx",
  "doc_id": "doc_xxx",
  "status": "queued",
  "storage_uri": "s3://visior-documents/tenant/doc.bin"
}
```
Действия:
1) Сохраняет файл в S3 или `local://`.
2) Создаёт job в `JobStore`.
3) Опционально регистрирует документ в Document Service (`/internal/documents`).
4) Запускает фоновой pipeline (`process_file`) через `BackgroundTasks`.

### POST `/internal/ingestion/status`
Тело: `{"job_id": "...", "status": "...", "error": null}`.
Обновляет job и, если задан `DOC_SERVICE_BASE_URL`, пушит статус в Document Service (`/internal/documents/status`).

## Pipeline `process_file`
Выполняется в фоне (не блокирует ответ `/enqueue`).
1. `download_bytes` — получает файл из S3/local.
2. `split_chunks` — простое разбиение текста на фрагменты (≈2048 символов), далее считаем chunk=section (упрощённо).
3. Строит 3 уровня эмбеддингов через `EmbeddingClient`:
   - document (целый текст),
   - section (по каждому chunk),
   - chunk (сейчас совпадает с section).
   В mock-режиме — псевдо-эмбеддинги по SHA256.
4. Формирует payload секций (section_id, title, page_start/end, chunk_ids, summary, embedding).
5. Отправляет секции и статус `indexed` в Document Service, если указан `DOC_SERVICE_BASE_URL`.
6. Обновляет job: `indexed` (или `failed` + error).

## Docker Compose (локальная разработка)
- MinIO (`minio`, `minio-setup`) создаёт бакет `visior-documents` на `http://localhost:9000` (консоль :9001).
- Ingestion и Document сервисы сконфигурированы на MinIO, но остаются в `MOCK_MODE=true`.
- Redis добавлен для будущей очереди (пока не используется).

## Планы развития (v2)
- Заменить `InMemoryJobStore` на реальный брокер (SQS/Kafka/Redis Queue).
- Добавить полноценный парсер (PDF/DOCX) и выделение секций/page ranges.
- Разнести chunk и section (сейчас это одно и то же).
- Отправлять события `document_ingested`/`ingestion_failed` в шину.
- Покрыть интеграционными тестами с MinIO/Testcontainers.
- Конфигурируемый размер chunk/token budget и max pages/size.

## Быстрый старт локально
```bash
docker compose up --build
# или без Docker:
cd services/ingestion_service
export INGEST_MOCK_MODE=true
pip install -e '.[dev]'
uvicorn ingestion_service.main:app --reload --port 8050
```

## Проверка
- `pytest` из корня — 29 тестов зелёные (включая ingestion).
- `/internal/ingestion/enqueue` — возвращает job_id + storage_uri; в фоне pipeline обновит job и Document Service (если настроен).
