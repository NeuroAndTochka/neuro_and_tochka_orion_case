# Document Service

## Назначение
Хранит метаданные документов/секций/тегов, выдаёт ссылки на файл и принимает статусы/результаты от Ingestion Service. Работает на async SQLAlchemy (SQLite по умолчанию) с S3/MinIO клиентом или локальным storage.

## Эндпоинты (`/internal/documents`)
- `POST /internal/documents` — создание/обновление документа (поля: `doc_id`, `tenant_id`, `name`, `status`, опц. `product`, `version`, `storage_uri`, `pages`, `tags`).
- `GET /internal/documents` — список с фильтрами `status|product|tag|search`, `limit/offset`; требует `X-Tenant-ID`. Ответ `{total, items}`.
- `GET /internal/documents/{doc_id}` — detail (включая sections/tags), требует `X-Tenant-ID`.
- `GET /internal/documents/{doc_id}/sections/{section_id}` — секция.
- `POST /internal/documents/{doc_id}/sections` — батч upsert секций ingestion-пайплайном.
- `POST /internal/documents/status` — обновление статуса/ошибки/страниц (tenant определяется по doc_id).
- `GET /internal/documents/{doc_id}/download-url` — временная ссылка на файл (локальный путь или S3 pre-signed). Требует `X-Tenant-ID`.
- `/health` — `{"status":"ok"}`.

## Конфигурация (`DOC_*`)
`mock_mode` (по умолчанию true), `db_dsn` (SQLite by default), `s3_endpoint/access_key/secret_key/bucket/region/secure`, `local_storage_path`, `download_url_expiry_seconds`, `host/port/log_level`. При `mock_mode=false` сервис требует непустые S3 креды и не-SQLite DSN.

## Реализация
- Таблицы: `documents`, `document_sections`, `document_tags`; soft-delete через `deleted_at`.
- Tenant isolation: все операции чтения требуют `X-Tenant-ID` и проверяют совпадение tenant в БД.
- StorageClient поддерживает `s3://`, `local://`, `file://`; локальный режим использует папку из `local_storage_path`.
