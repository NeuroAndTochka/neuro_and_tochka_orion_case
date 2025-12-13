# Document Service — progress

## Что уже реализовано
- Эндпоинты `/internal/documents` (list/get), `/internal/documents/{doc_id}`, `/internal/documents/{doc_id}/sections/{section_id}`, `/internal/documents/{doc_id}/sections` (upsert), `/internal/documents/status`, `/internal/documents/{doc_id}/download-url`, `/health` на FastAPI (`routers/documents.py`).
- Модели данных и схемы: документы, секции, теги (`models.py`, `schemas.py`), tenant isolation на уровне запросов (обязательный `X-Tenant-ID` для get/list/section/download).
- Репозиторий CRUD с фильтрами `status/product/tag/search`, upsert секций и обновление статуса/страниц/ошибки ingestion (`core/repository.py`).
- Хранилище: генерация download URL для `s3://`, `local://` и `file://`, локальное хранилище в mock-режиме (`storage.py`).
- Конфиг через `DOC_*` (`config.py`), проверка прод-конфига (PostgreSQL DSN + S3 креды) при `mock_mode=false`; логирование structlog.
- Тесты: юнит/интеграция на SQLite + локальное хранилище (`tests/test_documents.py`) и CRUD тест репозитория на PostgreSQL через testcontainers или внешний DSN (`tests/test_postgres_repository.py`).

## Как это реализовано
- Приложение инициализирует Async SQLAlchemy engine/session и StorageClient в lifespan (`main.py`), создаёт таблицы при старте (`init_db`).
- DocumentRepository строит SQLAlchemy запросы с selectinload для тэгов/секций; список документов сортируется по `updated_at` с limit/offset.
- Tenant isolation: list/get/section/download получают `tenant_id` из заголовка; статус и create не требуют заголовка, но репозиторий проверяет tenant при конфликте и возвращает 404/PermissionError.
- Upsert секций перезаписывает все переданные секции (создаёт/обновляет по `section_id`), теги всегда пересоздаются на create/update.
- Download URL: для `s3://` генерируется presigned URL (требует настроенный S3 клиент), для `local://` строится `file://` из `DOC_LOCAL_STORAGE_PATH`.

## Что осталось сделать / отклонения от ТЗ
- Нет кэша (Redis) для частых запросов, нет service token/аутентификации и проверки ролей; X-Request-ID не используется.
- Status endpoint не batch, не валидирует допустимые статусы/переходы; create/status не требуют `X-Tenant-ID`, хотя ТЗ подразумевает строгий контроль.
- Нет поддержки версионности документов (`document_versions`), soft-delete частично (deleted_at) не используется в API кроме фильтра list/get.
- Фильтры/поиск ограничены: поиск только по имени (LIKE), нет пагинации/фильтров секций, нет сортировки по полям, нет полного текста/тегов поиска как в ТЗ.
- Наблюдаемость: нет метрик, трассировки, audit-логов; rate limiting отсутствует.
- Политики безопасности/лимиты на размер storage_uri/sections/тегов не валидируются; загрузка/обновление не проверяет, что `storage_uri` валиден/принадлежит tenant.
