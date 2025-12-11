# Document Service

## Назначение
Document Service отвечает за хранение метаданных документов, секций и статусов ingestion. Через него API Gateway, Retrieval, MCP Tools Proxy и Ingestion Service получают единый источник правды о документах, сохраняя tenant isolation.

## Архитектура
- FastAPI приложение (`services/document_service`).
- Async SQLAlchemy + PostgreSQL для метаданных (`documents`, `document_sections`, `document_tags`).
- Хранилище контента — внешнее S3/MinIO, сервис хранит только `storage_uri`.
- StorageClient умеет выдавать pre-signed URL (S3) и локальные ссылки (`local://`) для mock режима.
- Конфигурация через `DOC_*` переменные, Pydantic Settings. Есть `mock_mode` для локальных тестов (SQLite + файловая папка).

## Конфигурация (ENV)
| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `DOC_HOST`, `DOC_PORT` | `0.0.0.0`, `8060` | Сетевые параметры сервиса |
| `DOC_LOG_LEVEL` | `info` | Уровень логирования structlog |
| `DOC_MOCK_MODE` | `true` | Если `true` — SQLite + локальное хранилище (используется в тестах) |
| `DOC_DB_DSN` | `sqlite+aiosqlite:///./document_service.db` | DSN. В проде должен быть `postgresql+asyncpg://` |
| `DOC_S3_ENDPOINT` | `null` | MinIO/совместимый эндпоинт (optional для AWS) |
| `DOC_S3_BUCKET` | `null` | Бакет для хранения файлов |
| `DOC_S3_ACCESS_KEY`/`DOC_S3_SECRET_KEY` | `null` | Креды S3/MinIO |
| `DOC_S3_REGION` | `us-east-1` | Регион S3 |
| `DOC_S3_SECURE` | `true` | Использовать HTTPS при работе с S3 |
| `DOC_LOCAL_STORAGE_PATH` | `./.document_storage` | Папка для mock режима / локального fallback |
| `DOC_DOWNLOAD_URL_EXPIRY_SECONDS` | `300` | TTL pre-signed URL |

> При `DOC_MOCK_MODE=false` сервис валидирует конфигурацию и требует PostgreSQL DSN + настройки S3/MinIO. Это защищает от запуска в бою с локальными заглушками.

## Рабочие режимы
1. **Production** — `DOC_MOCK_MODE=false`, `DOC_DB_DSN=postgresql+asyncpg://...`, заданы `DOC_S3_*`. Сервис создаёт подключения к БД и к S3, local storage не используется.
2. **Local / Tests** — `DOC_MOCK_MODE=true` (значение по умолчанию). Используется SQLite файл и папка `DOC_LOCAL_STORAGE_PATH`. Тесты `pytest services/document_service/tests/test_documents.py` автоматически создают/очищают файл БД и директорию сториджа.

Переход от локального к прод окружению не требует правок кода: достаточно переключить переменные.

## API
Все вызовы требуют заголовка `X-Tenant-ID`. Сервис делает строгую проверку tenant (документ не выдаётся, если принадлежит другому tenant).

### `POST /internal/documents`
Создание / обновление метаданных (ingestion, API Gateway).
```json
{
  "doc_id": "doc_ab12",
  "tenant_id": "tenant_1",
  "name": "Orion LDAP Guide",
  "product": "Orion Core",
  "version": "1.2",
  "status": "uploaded",
  "storage_uri": "s3://visior-documents/tenant_1/doc_ab12/original.pdf",
  "tags": ["ldap", "admin"]
}
```
Возвращает `DocumentDetail`.

### `GET /internal/documents`
Фильтры: `status`, `product`, `tag`, `search`, `limit`, `offset`.
```bash
curl -H "X-Tenant-ID: tenant_1" \
  "http://localhost:8060/internal/documents?status=indexed&limit=20"
```
Ответ — `DocumentListResponse` с пагинацией.

### `GET /internal/documents/{doc_id}`
Детальная карточка документа, включая секции, страницы и `storage_uri`. Возвращает 404, если tenant не совпадает.

### `GET /internal/documents/{doc_id}/sections/{section_id}`
Отдаёт конкретную секцию `DocumentSection` (page range, chunk_ids, summary).

### `POST /internal/documents/{doc_id}/sections`
Используется ingestion для записи секций/результатов парсинга. Полностью upsert-ит переданный список (по `section_id` внутри документа).

### `POST /internal/documents/status`
Обновление статуса ingest pipeline (indexed, failed, processing), страниц и `storage_uri`. Возвращает актуальный `DocumentDetail` после изменения.

### `GET /internal/documents/{doc_id}/download-url`
Генерирует URL для скачивания. В проде возвращает S3 pre-signed ссылку, в mock режиме — `file://` путь в локальном сторидже. Ошибки S3 транслируются в `400`.

## Интеграции
| Сервис | Направление | Детали |
| --- | --- | --- |
| API Gateway | REST | Листинг документов, отдача детальной карточки для UI |
| Ingestion Service | REST | `POST /internal/documents/status` и `/sections` после обработки исходных файлов |
| Retrieval Service | REST | Берёт секции и chunk_ids для формирования индекса |
| MCP Tools Proxy | REST | Проверяет доступность документа и диапазонов перед вызовом MCP |

## Тестирование
- **Unit/Integration** – `pytest services/document_service/tests/test_documents.py` прогоняет все API сценарии c TestClient, SQLite и локальной папкой.
- **pre-commit** – flake8, end-of-file, trim trailing whitespace.
- Для продовых интеграционных тестов планируется использовать docker-compose (PostgreSQL + MinIO) или Testcontainers.

## Наблюдаемость
- Логирование через structlog (`document_service.logging`). Каждый запрос инициализируется с указанием `tenant_id`, `doc_id`.
- Health-check `GET /health`.
- TODO: добавить метрики (Prometheus) и аудит.

## Расширение
- Добавляя поля в схемы, обновляйте `document_service/models.py`, `schemas.py`, тесты и открытые спецификации (`docs/document_service_spec.md`, `docs/frontend_api.md`).
- Для новых эндпоинтов придерживайтесь `X-Tenant-ID` и структуры ответов `DocumentDetail` / `DocumentSection`.
