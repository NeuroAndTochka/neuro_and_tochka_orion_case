# Ingestion Service

## Назначение
Ingestion Service принимает файлы от API Gateway, ставит задания на обработку и обновляет их статусы. Сервис выступает буфером перед пайплайном парсинга и индексации.

## Архитектура
- FastAPI (`services/ingestion_service`).
- Очередь InMemory (`core/storage.InMemoryQueue`). В проде заменяется на БД/очередь.
- Конфигурация через `INGEST_*`.

## Конфигурация
| Переменная | Описание |
| --- | --- |
| `INGEST_STORAGE_PATH` | Путь для хранения файлов (production default — `/var/lib/visior_ingestion_storage`; в mock-режиме автоматически используется `/tmp/visior_ingestion_storage`). |
| `INGEST_MOCK_MODE` | Включить in-memory очередь. |

## API
Все запросы требуют заголовок `X-Tenant-ID`.

### `POST /internal/ingestion/enqueue`
Multipart запрос.

```bash
curl -H "X-Tenant-ID: tenant_1" -F "file=@spec.pdf" -F "product=IAM" \
  http://ingest.local/internal/ingestion/enqueue
```
**Response**
```json
{
  "job_id": "job-123",
  "doc_id": "doc_1",
  "status": "queued"
}
```

### `POST /internal/ingestion/status`
Body:
```json
{
  "job_id": "job-123",
  "status": "processing",
  "error": null
}
```
Возвращает обновлённый `EnqueueResponse`.

## Расширение
- Реальная очередь может писаться в S3/SQS/Kafka. В этом случае замените `InMemoryQueue` на адаптер и обновите `get_queue`.
- Новые статусы (например, `parsing`, `embedding`) необходимо задокументировать и добавить в `schemas.StatusPayload`.

## Mock требования
- В mock режиме очередь должна поддерживать полный цикл `queued -> processing -> done/failed`.
- Любое новое поле в ответе (например `estimated_time_ms`) добавляйте в mock `Ticket` и `tests/test_ingestion.py`.
