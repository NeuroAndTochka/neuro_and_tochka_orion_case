# ML Observer Service

## Назначение
Playground/консоль для ML-команды: хранит эксперименты и результаты, проксирует вызовы ingestion/doc/retrieval/orchestrator, позволяет сделать dry-run LLM, содержит простую UI-страницу `/ui`. БД — SQLite по умолчанию.

## Эндпоинты (`/internal/observer`)
- Эксперименты: `POST /experiments` (создание), `GET /experiments/{experiment_id}` (detail). Требует `X-Tenant-ID`.
- Документы: `POST /documents/upload` (upsert записи), `GET /documents/{doc_id}` (detail в локальной БД).
- Ingestion proxy: `POST /ingestion/enqueue`, `POST /ingestion/status`, `GET /ingestion/jobs/{job_id}` — работают если задан `ingestion_base_url`.
- Документы/дерево: `GET /documents` (список из Document Service), `GET /documents/{doc_id}/detail`, `GET /documents/{doc_id}/tree` (через Ingestion Service), требуют базовые URL.
- Summarizer/chunking config: `GET/POST /summarizer/config`, `GET/POST /chunking/config` (прокси в ingestion).
- Retrieval: `POST /retrieval/run` (генерация моковых hits и метрик), `POST /retrieval/search` (прокси в Retrieval Service), `GET/POST /retrieval/config`.
- LLM: `POST /llm/dry-run` (mock), Orchestrator: `POST /orchestrator/respond` (прокси в AI Orchestrator).
- UI: `GET /ui` — статическая HTML страница.

## Конфигурация (`OBS_*`)
`db_dsn` (SQLite default), `mock_mode`, `ingestion_base_url`, `document_base_url`, `retrieval_base_url`, `orchestrator_base_url`, `host/port/log_level`. При `mock_mode=false` сервис требует не-SQLite DSN.

## Особенности
- Все запросы кроме UI требуют заголовок `X-Tenant-ID`.
- Прокси вызовы оборачивают ошибки downstream в HTTPException с тем же статусом.
