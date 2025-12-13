# ML Observer Service — progress

## Что уже реализовано
- FastAPI приложение с `/health`, статическим UI `/ui` и основными internal ручками в `routers/observer.py` (создание экспериментов/ранов/документов, mock retrieval/LLM/playground прокси в ingestion/doc).
- Конфиг `OBS_*` (`config.py`): mock_mode (по умолчанию true), allowed_tenant, DSN БД, базовые URL зависимостей (ingestion/document/retrieval/llm), параметры MinIO (зарезервированы).
- SQLite по умолчанию, прод-режим требует внешний DSN; инициализация БД/Session в `main.py` (lifespan), логирование structlog.
- Репозиторий (`core/repository.py`) с CRUD: create/get experiment, add run, upsert/get document статусов; mock retrieval hits generator.
- Схемы моделей и API (`schemas.py`, `models.py`), миграция таблиц при старте (`db.py`).
- Тесты на базовые сценарии API (`services/ml_observer/tests`).

## Как это реализовано
- App при старте создаёт engine/session_factory, выполняет `init_db`, кладёт `settings`/`repository` в `app.state`, подключает роутеры.
- ObserverRepository сохраняет эксперименты/раны/документы в SQLAlchemy моделях, возвращает pydantic-схемы; mock retrieval генерирует до 5 фиктивных хитов с метриками.
- Прокси в ingestion/document (зависит от настроек URL) выполняется через httpx; retrieval/LLM dry-run реализованы моками.
- UI served из `routers/ui.py` (статический HTML).

## Что осталось сделать / отклонения от ТЗ
- Retrieval/LLM интеграции сейчас полностью mock; MinIO/артефакты не используются, несмотря на конфиг поля.
- Безопасность: нет аутентификации/service token, проверка tenant только на allowed_tenant; UI доступен без ограничений.
- Ограничена функциональность UI/наблюдаемости: нет дашбордов, нет метрик/трейсинга; health не проверяет зависимые сервисы/БД.
- Прокси-зависимости (ingestion/document) не имеют fallback/retry и не описаны полностью в документации; retrieval_base_url/llm_base_url зарезервированы, но не задействованы.
