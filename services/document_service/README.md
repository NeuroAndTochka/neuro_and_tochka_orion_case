# Document Service

Метаданные документов и статусы ingestion для Orion Visior. FastAPI + async SQLAlchemy, PostgreSQL для метаданных и S3/MinIO для хранения файлов (сервис оперирует только ссылками). Подробная спецификация — `docs/document_service_spec.md`, технический план — `docs/document_service_technical_plan.md`.

## Возможности
- CRUD метаданных документов и секций (`/internal/documents`).
- Обновление статусов ingestion и ссылок на хранилище.
- Генерация download URL (S3 pre-signed или `file://` в mock режиме).
- Tenant isolation на уровне API.

## Быстрый старт (локально)
```bash
cd services/document_service
python -m venv .venv
source .venv/bin/activate
pip install -e .
export DOC_MOCK_MODE=true
uvicorn document_service.main:app --reload
```
Mock режим использует SQLite (`./document_service.db`) и папку `DOC_LOCAL_STORAGE_PATH` (по умолчанию `./.document_storage`). Подходит для разработки и unit-тестов.

## Production режим
```bash
export DOC_MOCK_MODE=false
export DOC_DB_DSN="postgresql+asyncpg://user:pass@postgres:5432/documents"
export DOC_S3_ENDPOINT="http://minio:9000"        # или пусто для AWS
export DOC_S3_BUCKET="visior-documents"
export DOC_S3_ACCESS_KEY="minio"
export DOC_S3_SECRET_KEY="minio-secret"
uvicorn document_service.main:app --host 0.0.0.0 --port 8060
```
При `DOC_MOCK_MODE=false` сервис проверит, что указан PostgreSQL DSN и заданы все S3 параметры, иначе упадёт на старте — это защищает прод от случайного запуска с локальными заглушками.

## Основные переменные окружения
| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `DOC_HOST` / `DOC_PORT` | `0.0.0.0` / `8060` | Адрес/порт HTTP |
| `DOC_LOG_LEVEL` | `info` | Уровень логирования |
| `DOC_MOCK_MODE` | `true` | SQLite + локальный storage |
| `DOC_DB_DSN` | `sqlite+aiosqlite:///./document_service.db` | DSN (в проде — PostgreSQL) |
| `DOC_S3_ENDPOINT` | `null` | URL MinIO/S3 совместимого API |
| `DOC_S3_BUCKET` | `null` | Бакет для файлов |
| `DOC_S3_ACCESS_KEY` / `DOC_S3_SECRET_KEY` | `null` | Креды для MinIO/S3 |
| `DOC_LOCAL_STORAGE_PATH` | `./.document_storage` | Папка mock режима |
| `DOC_DOWNLOAD_URL_EXPIRY_SECONDS` | `300` | TTL download ссылки |

Полный список в `document_service/config.py`.

## Тесты
```bash
cd services/document_service
./run_tests.sh
```
Тесты используют TestClient, SQLite и временную директорию в `tests/local_storage`. Перед запуском убеждайтесь, что активирован `DOC_MOCK_MODE=true` (значение задаётся в тесте автоматически).

## Docker
```bash
cd services/document_service
docker build -t visior-document-service .
docker run --rm -p 8060:8060 \
  -e DOC_MOCK_MODE=true \
  visior-document-service
```
Для боевого контейнера пробрасывайте Postgres/S3 переменные аналогично разделу «Production режим». В docker-compose сервис можно связать с MinIO и PostgreSQL сервисами.
