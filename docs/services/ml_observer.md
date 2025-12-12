# ML Observer Service

## Назначение
ML Observer — служебный сервис‑песочница для ML/IR команды. Он позволяет:
- загружать тестовые документы и прогонять их через ingestion → document → retrieval пайплайн без влияния на прод;
- управлять параметрами retrieval/rerank (k, фильтры, модели) и сравнивать пресеты;
- запускать A/B эксперименты и видеть metrikи (latency, precision, coverage);
- просматривать промежуточные артефакты (chunks, скоры reranker'а) и логи пайплайна.

Сервис нужен для быстрого тюнинга, регрессионных проверок и демонстраций качества без деплоя нового кода в основной backend.

## Архитектура
- FastAPI backend (`services/ml_observer`) + lightweight frontend (FastAPI templates или panel/Streamlit) для UI.
- Отдельная PostgreSQL база (`observer_db`) для хранения экспериментов, пресетов и результатов прогона.
- Доступ к staging MinIO/S3 бакету (`observer-artifacts`) и к публичным API существующих сервисов (ingestion, document, retrieval, llm).
- Очередь фоновых задач (FastAPI BackgroundTasks / Celery) для длительных прогонов.
- Конфигурация через `OBS_*` переменные.

```
Frontend UI → ML Observer API → (Ingestion → Document → Retrieval → LLM)
                               ↘ PostgreSQL (experiments)
                               ↘ MinIO (test artifacts)
```

## Основные сценарии
1. **Test Upload.** Пользователь загружает документ + параметры обработки → сервис вызывает ingestion API с отдельным tenant `observer_tenant` и отслеживает статус до индексации.
2. **Retrieval Playground.** UI позволяет выбрать документ/датасет, задать `top_k`, фильтры по тегам, веса rerank → API делает запрос в Retrieval Service и отображает чанки, оценки, rerank результат.
3. **Parameter Experiments.** Пользователь создает эксперимент (описание, параметры, запросы). Сервис выполняет серию запусков, сохраняет метрики и строит отчеты.
4. **Rerank/LLM Debug.** Возможность запустить LLM Service на сохраненном контексте и сравнить ответы разных конфигураций.
5. **Веб-интерфейс.** Встроенная страница `/ui` (статический HTML+JS) для проверки health, быстрого создания экспериментов, mock-загрузки документов, запуска retrieval и LLM dry-run вручную. Требует заголовок `X-Tenant-ID` (по умолчанию `observer_tenant`).

## Конфигурация
| Переменная | Описание |
| --- | --- |
| `OBS_HOST` / `OBS_PORT` | Параметры HTTP сервера. |
| `OBS_LOG_LEVEL` | Уровень логов. |
| `OBS_DB_DSN` | DSN PostgreSQL для хранения экспериментов. |
| `OBS_MINIO_ENDPOINT`, `OBS_MINIO_BUCKET`, `OBS_MINIO_ACCESS_KEY`, `OBS_MINIO_SECRET_KEY` | Стаджинг бакет для тестовых артефактов. |
| `OBS_DOCUMENT_BASE_URL`, `OBS_INGESTION_BASE_URL`, `OBS_RETRIEVAL_BASE_URL`, `OBS_LLM_BASE_URL` | URL внутренних сервисов (используем staging окружение). |
| `OBS_ALLOWED_TENANT` | Специальный tenant (например, `observer_tenant`). |
| `OBS_AUTH_TOKEN` | Service‑token для походов в другие сервисы. |

## API (черновой список)
- `POST /internal/observer/documents/upload` — принимает файлы/метаданные, создаёт ingestion задачу на `observer_tenant`, возвращает `experiment_id` и статус.
- `GET /internal/observer/documents/{experiment_id}` — показывает прогресс и ссылки на документ/секции из Document Service.
- `POST /internal/observer/retrieval/run` — тело: `{"queries": [...], "top_k": 10, "filters": {...}, "rerank": {"model": "...", "lambda": 0.5}}`. Возвращает список хитов с подробными метриками и ссылками на чанки.
- `POST /internal/observer/experiments` — создаёт эксперимент (название, параметры, набор запросов). Сервис запускает фоновую задачу, прогресс доступен через `GET /internal/observer/experiments/{id}` и `GET /internal/observer/experiments/{id}/results`.
- `POST /internal/observer/llm/dry-run` — позволяет протестировать ответ LLM на выбранном контексте (указывается `doc_id`, `section_ids`, prompt overrides).

Все endpoint'ы защищены internal auth (например, JWT с ролью `ml_observer`) и никогда не доступны из внешнего API Gateway.

## Взаимодействие с другими сервисами
| Сервис | Использование |
| --- | --- |
| Ingestion Service | Загрузка тестовых документов, отслеживание статусов. |
| Document Service | Чтение метаданных/секций для отображения в UI. |
| Retrieval Service | Выполнение поисковых запросов с произвольными параметрами. |
| LLM Service | Проверка генерации на сохраненном контексте, сравнение моделей. |
| MinIO | Хранение загруженных тестовых файлов и артефактов экспериментов. |

Все вызовы выполняются через существующие REST API, никаких прямых подключений к базам боевых сервисов.

## Режимы работы
- **Staging/Playground** — основной сценарий. Реальные ключи к staging MinIO/PostgreSQL, доступ открыт только ML/IR командам.
- **Local Dev** — `OBS_DB_DSN=sqlite+aiosqlite:///observer.db`, S3 заменяется на локальную папку `OBS_LOCAL_STORAGE_PATH`. Поднимается через `docker-compose` вместе с mock версиями зависимостей.

## Безопасность и аудит
- Каждый запрос логируется с `user_id`, `experiment_id`, `tenant`. Загруженные документы маркируются как тестовые (`observer_tenant`).
- Сервис никогда не пишет в продовые бакеты/БД Document Service.
- При выгрузке результатов поддерживается маскирование PII (опционально).

## Расширение
- Новые типы экспериментов (например, сравнение rerank моделей) оформляем через отдельные job handlers и таблицы в БД.
- Для интеграции с внешними визуализациями можно добавить WebSocket канал или экспорт в Prometheus/Grafana.
- Перед добавлением нового endpoint'а синхронизируемся с ML командой, чтобы не дублировать функциональность в API Gateway.
