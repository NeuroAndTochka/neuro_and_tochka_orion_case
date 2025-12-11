# Техническое проектирование: Document Service

## 1. Цель
Разработать production-ready Document Service, который:
- хранит метаданные документов и секций в PostgreSQL;
- хранит контент (PDF/DOCX) и связанные артефакты в S3-совместимом MinIO;
- предоставляет REST API для доступа к документам и обновления статусов ingestion;
- обеспечивает tenant isolation, кэширование и аудит;
- имеет локальный режим (SQLite + локальная папка) для разработчиков.

## 2. Архитектура
```
API Gateway / Retrieval / MCP → Document Service → PostgreSQL (metadata)
                                            ↘ MinIO (storage)
                                            ↘ Redis (optional cache)
```
- FastAPI приложение (`services/document_service`).
- SQLAlchemy/asyncpg для PostgreSQL.
- Storage-клиент (S3 API) для MinIO.
- Dependency overrides для локального режима (SQLite + файловая папка).

## 3. Данные и модели
### Таблицы PostgreSQL
1. `documents`
   - `doc_id` UUID (PK)
   - `tenant_id`
   - `name`, `product`, `version`
   - `status` (`uploaded`, `processing`, `indexed`, `failed`)
   - `storage_uri` (путь в S3/MinIO)
   - `created_at`, `updated_at`, `deleted_at`
2. `document_sections`
   - `section_id` UUID (PK)
   - `doc_id` FK → `documents`
   - `title`, `page_start`, `page_end`, `summary`
   - `chunk_ids` JSONB
3. `document_tags`
   - `doc_id`
   - `tag`
4. `document_audit`
   - `event_id`, `doc_id`, `action`, `performed_by`, `performed_at`

### Storage (MinIO)
- Бакет: `visior-documents`.
- Ключи вида: `tenant_id/doc_id/original.pdf` + `tenant_id/doc_id/sections/section_id.json` (при необходимости).
- Метаданные о ключах хранятся в `storage_uri` и `document_sections.storage_path`.

## 4. API и флоу
1. `GET /internal/documents` — список с фильтрами + пагинация (limit/offset, сортировка по дате).
2. `GET /internal/documents/{doc_id}` — информация о документе + секции.
3. `GET /internal/documents/{doc_id}/sections/{section_id}` — конкретная секция.
4. `POST /internal/documents/status` — обновление статуса (ingestion → ready/failed) и запись `storage_uri`.
5. `POST /internal/documents/{doc_id}/sections` — сохранение секций/summary (вызывается ingestion pipeline).
6. `PUT /internal/documents/{doc_id}/tags` — управление тегами (опционально).
7. `GET /internal/documents/{doc_id}/download-url` — временная ссылка (pre-signed URL) для скачивания (не для фронта, только для BFF/MCP).

## 5. Технический стек
- Python 3.10+, FastAPI, Pydantic v2.
- SQLAlchemy 2.0 (async), asyncpg, Alembic для миграций.
- aiobotocore/boto3 для MinIO (S3 API).
- Redis (aioredis) — кэш (опционально в v1, но интерфейс заложить).
- pytest + pytest-asyncio, Testcontainers (PostgreSQL + MinIO) для интеграционных тестов.
- docker-compose: postgres + minio + сервис.

## 6. Конфигурация
| Переменная | Описание |
| --- | --- |
| `DOC_DB_DSN` | PostgreSQL DSN (prod/stage) или `sqlite+aiosqlite:///local.db` (dev) |
| `DOC_S3_ENDPOINT`, `DOC_S3_ACCESS_KEY`, `DOC_S3_SECRET_KEY`, `DOC_S3_BUCKET` | Настройки MinIO/S3 |
| `DOC_LOCAL_STORAGE_PATH` | Папка для локального хранения (только dev) |
| `DOC_CACHE_URL` | Redis URL (опционально) |
| `DOC_ENABLE_AUDIT` | Флаг аудита |

## 7. Сценарии окружений
### Production
- PostgreSQL (Managed или RDS).
- MinIO или совместимое S3-хранилище.
- Redis (кэш метаданных, TTL 5 минут).
- Kubernetes Deployment + ConfigMap/Secret для переменных.

### Local Developer Experience
- `docker compose up document_service` поднимает PostgreSQL и MinIO контейнеры.
- Скрипт `scripts/init_document_service.sh` создаёт миграции и тестовые данные.
- Возможен lightweight режим: SQLite + локальная папка (`DOC_LOCAL_STORAGE_PATH=./.local_storage`).
- Тесты используют Testcontainers или docker-compose (отдельная сеть).

## 8. Тестирование
1. **Unit**: репозитории, схемы, storage-клиент (mock S3).
2. **Integration**: запуск docker-compose (PostgreSQL + MinIO), прогон REST тестов через httpx/pytest.
3. **E2E**: связка ingestion → document_service → retrieval (добавить fixture для ingestion события).
4. **Performance**: нагрузка на `/internal/documents` при 10k документов / tenant.

## 9. План реализации (итерации)
1. **Итерация 1**: Скелет сервиса, CRUD по документам/секциям, PostgreSQL + миграции, локальное S3 mock.
2. **Итерация 2**: Storage-клиент для MinIO (загрузка/получение signed URL), интеграция с Ingestion Service, базовый кэш.
3. **Итерация 3**: Аудит, расширенные фильтры, оптимизации (индексы, caching), метрики.

## 10. Риски и меры
- **Consistency**: возможны гонки при обновлении статусов → использовать optimistic locking (version/timestamp).
- **Storage Failures**: предусмотреть retry + circuit breaker при временных ошибках S3.
- **Security**: шифрование секретов (JWT, access keys), ограничение TTL на pre-signed URL.
- **Scalability**: добавить индексы по `tenant_id`, `status`, `updated_at`; секции хранить батчами.

## 11. Вывод
Проект включает продовую реализацию Document Service на FastAPI + PostgreSQL + MinIO, покрыт тестами (unit/integration) и имеет локальный режим для разработчиков. После реализации сервис обеспечит единый источник данных для Gateway, Retrieval и MCP.

## 12. Статус реализации v1
На текущем этапе готов полноценный скелет сервиса, который можно подключать к продовому контуру:
- **FastAPI-приложение** `document_service.main` с async lifespan, инициализацией БД и storage-клиента. Конфигурация берётся из `Settings` (переменные `DOC_*`), есть переключение между SQLite/локальной папкой и продовым PostgreSQL+S3.
- **Схема БД**: SQLAlchemy 2.0 async-модели `Document`, `DocumentSection`, `DocumentTag` (см. `document_service.models`). Для секций используется составной PK (`doc_id`, `section_id`), теги уникализированы по паре `doc_id+tag`. Миграции будут добавлены позже, пока `init_db` создаёт таблицы автоматически.
- **Репозиторий** `DocumentRepository` реализует:
  - `create_or_update_document`, `list_documents` с фильтрами и пагинацией,
  - выборку документа и секции, upsert секций,
  - сервисный эндпойнт обновления статуса с фиксированной загрузкой тегов (чтобы избежать `MissingGreenlet`).
  Все методы асинхронные, используют `selectinload` для eager-загрузки связанных сущностей.
- **Storage-клиент** поддерживает `s3://`, `local://` и `file://` URI. В тестовом режиме документы сохраняются в `./services/document_service/tests/local_storage`, в проде можно указать MinIO через endpoint и креды.
- **API** (router `document_service.routers.documents`):
  1. `POST /internal/documents` — создание/обновление метаданных (403 при конфликте tenant).
  2. `GET /internal/documents` — листинг с query-параметрами `status`, `product`, `tag`, `search`, `limit`, `offset`.
  3. `GET /internal/documents/{doc_id}` и `/sections/{section_id}` — карточка документа и конкретная секция.
  4. `POST /internal/documents/{doc_id}/sections` — массовое обновление секций ingestion-пайплайном.
  5. `POST /internal/documents/status` — обновление статуса, страниц, ссылок хранения (используется ingestion/ai orchestrator).
  6. `GET /internal/documents/{doc_id}/download-url` — генерация URL (локальный `file://` или S3 pre-signed).
- **Тесты** `services/document_service/tests/test_documents.py` покрывают все эндпойнты: создание, листинг, detail, секции, статус, генерацию ссылок и проверку tenant isolation. Тесты используют SQLite и локальное хранилище, автоматически чистят временные файлы.
- **Интеграционные тесты** `services/document_service/tests/test_postgres_repository.py` запускают Testcontainers (PostgreSQL, образ задаётся `DOC_TEST_POSTGRES_IMAGE`, по умолчанию `postgres:16`) и прогоняют CRUD-цикл репозитория против реальной БД. Требуется Docker и новый dev-dependency `testcontainers`. Альтернатива — задать `DOC_TEST_POSTGRES_DSN`, чтобы тесты использовали подготовленный Postgres (например, в GitHub Actions или локальном Docker Compose).
- **Интеграция с CI**: `pre-commit` и `flake8` проходят, тесты `pytest services/document_service/tests/test_documents.py` зелёные.

Следующие шаги: добавить Alembic-мода, интеграционные тесты с Postgres+MinIO (testcontainers), аудит и кеширование, а также документацию OpenAPI для фронта.
