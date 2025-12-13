# ML Observer Service

## Назначение
ML Observer — служебная песочница для ML/IR. Текущая реализация хранит эксперименты/прогоны в БД и даёт ручки/UI для ручных запусков ingestion/retrieval/LLM (retrieval/LLM сейчас mock). Нужен для отладки и демонстраций без влияния на прод.

## Архитектура
- FastAPI (`services/ml_observer`) + статический HTML UI `/ui`.
- Хранение: SQLite по умолчанию; в prod-режиме требуется внешний PostgreSQL DSN.
- Эксперименты/раны/документы — таблицы в локальной БД (SQLAlchemy).
- Прокси в ingestion/doc сервисы (если заданы `OBS_INGESTION_BASE_URL` / `OBS_DOCUMENT_BASE_URL`); retrieval/LLM сейчас мокируются.
- Конфигурация через `OBS_*`.

```
Frontend → ML Observer API → (Ingestion → Document)*
                         ↘ SQLite/PostgreSQL (experiments)
* Retrieval/LLM — сейчас mock
```

## Основные сценарии
1. Создание эксперимента (`POST /internal/observer/experiments`) и просмотр карточки (`GET .../{id}`) — хранение в БД.
2. Mock загрузка документа (`POST /internal/observer/documents/upload`) — запись статуса в БД без реального файла.
3. Проксирование ingestion: `/internal/observer/ingestion/enqueue|status` (работает при заданном `OBS_INGESTION_BASE_URL`).
4. Проксирование Document Service: список/деталь/дерево документа (при `OBS_DOCUMENT_BASE_URL`).
5. Retrieval playground: `/internal/observer/retrieval/run` — mock хиты + сохранение run.
6. LLM dry-run: `/internal/observer/llm/dry-run` — mock ответ + usage, сохраняет run.
7. UI `/ui` для ручных запусков (требуется заголовок `X-Tenant-ID`, дефолт `observer_tenant`).

## Конфигурация
| Переменная | Описание |
| --- | --- |
| `OBS_MOCK_MODE` | `true` по умолчанию; при `false` требуется PostgreSQL DSN (не SQLite). |
| `OBS_DB_DSN` | DSN БД экспериментов (`sqlite+aiosqlite:///./ml_observer.db` по умолчанию). |
| `OBS_ALLOWED_TENANT` | Допустимый tenant (дефолт — `observer_tenant`). |
| `OBS_INGESTION_BASE_URL` / `OBS_DOCUMENT_BASE_URL` | URL зависимых сервисов; без них ручки возвращают 503. |
| `OBS_RETRIEVAL_BASE_URL`, `OBS_LLM_BASE_URL` | Зарезервированы под реальные вызовы (сейчас mock). |
| `OBS_HOST` / `OBS_PORT` / `OBS_LOG_LEVEL` | Сетевые параметры и уровень логов. |
| `OBS_MINIO_*`, `OBS_LOCAL_STORAGE_PATH` | Зарезервировано под хранение артефактов; пока не используется. |

## API (черновой список)
- `POST /internal/observer/experiments`, `GET /internal/observer/experiments/{id}` — CRUD экспериментов (БД).
- `POST /internal/observer/documents/upload`, `GET /internal/observer/documents/{doc_id}` — сохранение статуса документа в БД.
- `POST /internal/observer/ingestion/enqueue`, `POST /internal/observer/ingestion/status` — прокси в Ingestion Service.
- `GET /internal/observer/documents` / `{doc_id}/detail` — прокси в Document Service; `/documents/{doc_id}/tree` — через Ingestion Service.
- `GET/POST /internal/observer/summarizer/config` — прокси настроек summarizer в Ingestion Service.
- `POST /internal/observer/retrieval/run` — mock хиты + сохранение run.
- `POST /internal/observer/llm/dry-run` — mock ответ + сохранение run.
- `/ui`, `/health` — UI и healthcheck.

## Взаимодействие с другими сервисами
| Сервис | Использование |
| --- | --- |
| Ingestion Service | Proxy upload/status, summarizer config, дерево документа. |
| Document Service | Proxy список/деталь документа. |
| Retrieval / LLM | Пока mock в коде; URL поля зарезервированы. |

## Режимы работы
- **Local/MOCK** — по умолчанию: SQLite, mock retrieval/LLM, прокси отключаются если URL не заданы.
- **Prod/Staging** — `OBS_MOCK_MODE=false`, требуется PostgreSQL DSN и реальные URL зависимых сервисов; retrieval/LLM нужно реализовать/подключить.

## Безопасность и аудит
- Аутентификация не реализована; доступ нужно ограничивать сетью/ingress. Каждый запрос требует `X-Tenant-ID`.
- Логи содержат tenant/experiment_id; допускается проверка на `OBS_ALLOWED_TENANT` на стороне окружения.

## Расширение
- Подключить реальные вызовы retrieval/LLM и хранение артефактов (MinIO).
- Добавить фоновые задачи/воркеры и richer UI (вебсокеты, дашборды).
- Перед добавлением новых endpoint'ов синхронизироваться с ML-командой, чтобы не дублировать API Gateway.
