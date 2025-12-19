# Technical Specification — Document Service

## 1. Purpose
Store document metadata (name/product/version/tags/status), sections and links to storage. Provide internal APIs for listing/reading documents and for ingestion pipeline to upsert sections/status. Default runtime is SQLite + local storage; when `mock_mode=false` the service requires Postgres DSN and S3/MinIO creds.

## 2. API (prefix `/internal/documents`)
- `POST /internal/documents` — create/update document metadata. Payload: `doc_id`, `tenant_id`, `name`, `status`, optional `product`, `version`, `storage_uri`, `pages`, `tags[]`.
- `GET /internal/documents` — list with filters `status|product|tag|search`, pagination `limit|offset` (requires `X-Tenant-ID`). Response `{total, items}`.
- `GET /internal/documents/{doc_id}` — detail with sections and tags (requires `X-Tenant-ID`).
- `GET /internal/documents/{doc_id}/sections/{section_id}` — section metadata (title, pages, chunk_ids, summary, storage_path).
- `POST /internal/documents/{doc_id}/sections` — batch upsert of sections from ingestion.
- `POST /internal/documents/status` — update status/error/pages/storage_uri; returns updated detail.
- `GET /internal/documents/{doc_id}/download-url` — generate download URL (local path or S3 pre-signed), requires `X-Tenant-ID`.
- `/health` — `{status: "ok"}`.

## 3. Data model (SQLAlchemy async)
- `documents`: `doc_id` (PK), `tenant_id`, `name`, `product`, `version`, `status`, `storage_uri`, `pages`, timestamps, `deleted_at`.
- `document_sections`: `section_id` (PK), `doc_id` FK, `title`, `page_start`, `page_end`, `chunk_ids` (JSON), `summary`, `storage_path`.
- `document_tags`: `doc_id`, `tag`.

## 4. Behaviour
- Tenant isolation: все операции чтения требуют `X-Tenant-ID` и проверяют принадлежность документа.
- `ensure_runtime_configuration` запрещает запуск в prod-режиме без Postgres DSN (не SQLite) и S3 параметров.
- StorageClient поддерживает `s3://`, `file://`, `local://`; в mock режиме ссылки строятся на локальную папку.

## 5. Configuration (`DOC_*`)
`app_name`, `host/port/log_level`, `mock_mode`, `db_dsn`, `cache_url?`, `s3_endpoint/access_key/secret_key/bucket/region/secure`, `local_storage_path`, `download_url_expiry_seconds`.

## 6. Testing
Юнит-тесты в `services/document_service/tests` покрывают CRUD, секции и генерацию ссылок (SQLite + локальное хранилище). Для prod режима требуется отдельное покрытие Postgres/S3.
