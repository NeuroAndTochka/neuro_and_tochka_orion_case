# Техническое проектирование: Document Service

## Текущее состояние
- FastAPI + async SQLAlchemy (`documents`, `document_sections`, `document_tags`), SQLite по умолчанию.
- StorageClient умеет `s3://`, `file://`, `local://`; при `mock_mode=false` сервис требует не-SQLite DSN и заданные S3 ключи/бакет.
- API: создание/обновление документа, листинг с фильтрами и пагинацией, detail/section, upsert секций, обновление статуса, выдача download URL.
- Tenant isolation на чтение через заголовок `X-Tenant-ID`; статус/sections не требуют заголовка, tenant берётся из БД.
- Тесты покрывают SQLite/локальный storage; миграции Postgres/S3-интеграции отсутствуют.

## План развития
1. **Миграции и prod-схема**: добавить Alembic, протестировать на Postgres, описать индексы (`tenant_id`, `status`, `updated_at`).
2. **Хранилище**: обвязка MinIO/S3 с retry и валидацией `storage_uri`; опциональный прелоад локальных файлов при `mock_mode=true` для интеграционных тестов.
3. **Аудит и кеш**: включить кэширование листинга (Redis) и аудит доступа к документам/секциям.
4. **Контракты**: синхронизировать API Gateway клиент (использует `/internal/documents/list`) с фактическими путями `/internal/documents`.
5. **Наблюдаемость**: метрики по операциям (list/detail/sections/status/download-url), логирование без текста документов.

## Риски
- Запуск в prod без корректных env → `RuntimeError` (остается механизм защиты).
- Отсутствие миграций Postgres может привести к расхождениям схемы.
- Нет авторизации на уровне сервиса; полагаемся на внутреннюю сеть и tenant isolation.
