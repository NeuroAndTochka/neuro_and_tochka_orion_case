# API Gateway — progress

## Что уже реализовано
- Все публичные маршруты из ТЗ: `/api/v1/health`, `/api/v1/auth/me`, `/api/v1/assistant/query`, `/api/v1/documents/upload`, `/api/v1/documents`, `/api/v1/documents/{doc_id}` (см. `api_gateway/main.py`, `api_gateway/routers/*`).
- Аутентификация через Bearer-токен и интроспекцию, профиль пользователя отдаётся в `/api/v1/auth/me`.
- Input safety вызывается перед обращением к AI Orchestrator; при статусе не `allowed|monitor` запрос блокируется.
- In-memory rate limit на пользователя/tenant с настраиваемым порогом; применяется на ассистенте и всех document-ручках.
- Прокси-доступ к ingestion/document сервисам для загрузки и просмотра документов; заголовки трассировки, tenant и user пробрасываются автоматически.
- Поддержан mock-режим: клиенты safety/orchestrator/ingestion/document и AuthClient умеют возвращать заглушки, что позволяет локально поднять gateway без зависимостей.

## Как это реализовано
- RequestContextMiddleware (`api_gateway/core/middleware.py`) генерирует/прокидывает `trace_id`, `tenant_id` и сохраняет их в `request.state` + заголовках ответа.
- AuthClient (`api_gateway/clients/auth.py`) вызывает OAuth2 introspection (URL/timeout задаются в `config.py`), после чего `bind_user_to_context` переносит данные пользователя в контекст запроса.
- RateLimiter (`api_gateway/core/rate_limit.py`) хранит временные метки в памяти процесса; ключ формируется в роутерах с префиксом эндпоинта и `tenant_id:user_id`.
- `/api/v1/assistant/query` (`api_gateway/routers/assistant.py`) собирает payload для safety (`query`, `channel`, `context` без `channel`, `meta.trace_id`, `user`), затем отправляет объединённый запрос в orchestrator с `trace_id`, `tenant_id`, `user`, `safety`.
- Документные маршруты (`api_gateway/routers/documents.py`) читают файл/метаданные из формы, добавляют `tenant_id` и вызывают ingestion; листинг/деталь используют `DocumentClient`, схемы ответов описаны в `api_gateway/schemas.py`.
- Конфигурация через `API_GATEWAY_*` переменные (`api_gateway/config.py`): базовые URL зависимостей, таймауты HTTP/Auth, CORS, rate limit и `mock_mode`.
- Покрытие тестами: unit-тесты роутов/лимитера (`services/api_gateway/tests`) и e2e-прогон ассистента с остальными сервисами (`tests/test_pipeline_integration.py`).

## Что осталось сделать / отклонения от ТЗ
- `POST /api/v1/documents/upload` сейчас возвращает только `doc_id` и `status` (`DocumentUploadResponse`), хотя ingestion (`/internal/ingestion/enqueue`) отдаёт и `job_id` (и `storage_uri`); ТЗ обещает `job_id+doc_id`.
- `DocumentClient.list_documents` ходит на `/internal/documents/list`, тогда как Document Service реализует `GET /internal/documents` (см. `document_service/routers/documents.py`); текущий вызов приведёт к 404.
- Лимит запросов задаётся на ключи конкретных эндпоинтов (`assistant:...`, `doc-list:...`), тогда как в ТЗ `API_GATEWAY_RATE_LIMIT_PER_MINUTE` описан как глобальный лимит на пользователя; нужна унификация логики ключей, если требуется общий потолок.
- Аутентификация проходит даже без настроенного introspection URL: AuthClient возвращает demo-пользователя, если URL не задан или включён mock-режим. Для соответствия заявлению «проверяет аутентификацию» в бою стоит требовать URL или отключать fallback.
