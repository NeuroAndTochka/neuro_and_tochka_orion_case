# ML Observer Service

Playground/observer для ML/IR команды. Позволяет запускать тестовые загрузки документов, эксперименты с retrieval/rerank и dry-run LLM, не затрагивая продовый контур.

## Быстрый старт (локально)
```bash
cd services/ml_observer
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
export OBS_MOCK_MODE=true
uvicorn ml_observer.main:app --reload --port 8085
```
По умолчанию используется SQLite (`./ml_observer.db`); переключить на PostgreSQL можно через `OBS_DB_DSN=postgresql+asyncpg://...`.

## Основные переменные
| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `OBS_HOST` / `OBS_PORT` | `0.0.0.0` / `8085` | Сетевые параметры |
| `OBS_LOG_LEVEL` | `info` | Уровень логирования |
| `OBS_MOCK_MODE` | `true` | Включает мок-ответы без реальных вызовов внешних сервисов |
| `OBS_DB_DSN` | `sqlite+aiosqlite:///./ml_observer.db` | DSN для БД экспериментов |
| `OBS_ALLOWED_TENANT` | `observer_tenant` | Tenant для тестовых действий |
| `OBS_INGESTION_BASE_URL`, `OBS_DOCUMENT_BASE_URL`, `OBS_RETRIEVAL_BASE_URL`, `OBS_LLM_BASE_URL`, `OBS_ORCHESTRATOR_BASE_URL` | Базовые URL зависимых сервисов (используются, если `mock_mode=false`) |
| `OBS_MINIO_ENDPOINT`, `OBS_MINIO_BUCKET`, `OBS_MINIO_ACCESS_KEY`, `OBS_MINIO_SECRET_KEY` | Настройки MinIO/S3 для артефактов (зарезервировано) |

## Эндпойнты (v1)
- `POST /internal/observer/experiments` — создать эксперимент.
- `GET /internal/observer/experiments/{experiment_id}` — карточка эксперимента с последними прогонами.
- `POST /internal/observer/documents/upload` — зарегистрировать тестовую загрузку документа (в mock режиме без реального файла).
- `GET /internal/observer/documents/{doc_id}` — статус загрузки.
- `POST /internal/observer/retrieval/run` — выполнить запрос/запросы, вернуть хиты и сохранить прогон.
- `POST /internal/observer/llm/dry-run` — прогнать LLM на переданном контексте, сохранить прогон.

Все запросы требуют заголовок `X-Tenant-ID` (по умолчанию `observer_tenant`).

## Тесты
```bash
cd services/ml_observer
pytest
```
Тесты используют SQLite и мок-ответы, внешний Docker/БД не требуются.

## Docker
```bash
cd services/ml_observer
docker build -t visior-ml-observer .
docker run --rm -p 8085:8085 -e OBS_MOCK_MODE=true visior-ml-observer
```
Для боевого запуска пробросьте `OBS_DB_DSN` (PostgreSQL) и URL зависимых сервисов.

### UI / интеграция со стэком
- В браузере откройте `http://localhost:8085/ui` — это консоль для быстрой проверки ingestion/retrieval.
- Для работы против сервисов из `docker-compose` задайте:
  - `OBS_RETRIEVAL_BASE_URL=http://retrieval_service:8040`
  - `OBS_INGESTION_BASE_URL=http://ingestion_service:8050`
  - `OBS_DOCUMENT_BASE_URL=http://document_service:8060`
  - `OBS_LLM_BASE_URL=http://llm_service:8090` (если нужен dry-run LLM)
  - `OBS_ORCHESTRATOR_BASE_URL=http://ai_orchestrator:8070` (для теста RAG+MCP)
- Убедитесь, что `X-Tenant-ID` в UI выставлен в `observer_tenant` (по умолчанию).
