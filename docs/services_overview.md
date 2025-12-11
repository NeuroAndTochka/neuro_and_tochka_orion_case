# Обзор микросервисов Orion

Документ фиксирует текущее состояние всех сервисов бэкенд‑платформы Orion, описывает их API, зависимости и правила расширения. Все сервисы написаны на FastAPI и запускаются как самостоятельные приложения, взаимодействуя между собой по HTTP. Для разработки достаточно Python 3.10, `poetry`/`pip` и `pytest`.

## API Gateway

**Назначение.** Edgе‑слой, проверяет авторизацию, применяет rate‑limit, вызывает input‑safety и оркестратор, а также проксирует операции с документами/ингестией.

**API.**
- `GET /api/v1/health` — healthcheck.
- `GET /api/v1/auth/me` — возвращает профиль текущего пользователя (через `get_current_user`).
- `POST /api/v1/assistant/query` — основной endpoint ассистента. Перед вызовом оркестратора вызывает safety input check, пробрасывает trace_id, user context и safety ответ вниз по цепочке.
- `POST /api/v1/documents/upload` — принимает файл и метаданные, записывает задание в ingestion service. Требуется `Authorization` и rate-limit.
- `GET /api/v1/documents` / `GET /api/v1/documents/{doc_id}` — список и детальная информация через document service.

**Взаимодействия.** Через `api_gateway.clients.*` ходит в safety, orchestrator, ingestion и document сервисы. Авторизация реализована через `AuthClient` (mock/introspection). Rate limits завязаны на `RateLimiter`.

**Настройки.** `services/api_gateway/api_gateway/config.py` — переменные `API_GATEWAY_*` (базовые URL зависимостей, таймауты, mock_mode и т.д.).

**Расширение.** Новые публичные функции оформляются в отдельных роутерах. Перед вызовами downstream‑сервисов нужно добавить клиентов/зависимости в `api_gateway.dependencies`. Для новых endpoint'ов обязательно покрытие тестами (`services/api_gateway/tests`) и обновление схем (`schemas.py`) и документации.

## Safety Service

**Назначение.** Два endpoint'а для input/output guard. Использует rule‑based проверки PII, ключевых слов и prompt injection.

**API.**
- `POST /internal/safety/input-check` — принимает `InputCheckRequest` (обязателен блок `user`, `query`, опциональные `channel/context/meta`). Возвращает `SafetyResponse` со статусами `allowed|transformed|blocked`.
- `POST /internal/safety/output-check` — принимает `OutputCheckRequest` (`user`, `query`, `answer`, список источников), работает аналогично.

**Настройки.** `SAFETY_SERVICE_*`: режим политики (`policy_mode`), блоклисты, включение PII‑sanitize.

**Расширение.** Вся логика в `core/evaluator.py`. Новые правила добавляются аккуратно, с тестами (`services/safety_service/tests`) на граничные кейсы. API считается внутренним, однако контракты с API Gateway и AI Orchestrator уже закреплены — не ломаем схемы без синхронизации.

## AI Orchestrator

**Назначение.** Основной контроллер пайплайна: принимает запросы от API Gateway, собирает контекст у retrieval, вызывает LLM service, делает output safety и возвращает диверсифицированный ответ с телеметрией.

**API.**
- `POST /internal/orchestrator/respond` — принимает `OrchestratorRequest` (query, trace_id, user/user_id+tenant_id, доп. поля), возвращает `OrchestratorResponse` с answer, sources, safety блоком и telemetry.

**Взаимодействия.**
- Retrieval service (`retrieval_url`) — ожидает `{"query": "...", "tenant_id": "..."}` и в ответ список `hits`.
- LLM service (`llm_url`) — передает payload RAG режима с подготовленным контекстом.
- Safety service (`safety_url`) — output check после генерации.

**Особенности.** При отсутствии `user` объект строится из полей `user_id/tenant_id`. Контекст рекомбинируется в `core/context_builder.py`. Любое расширение (например, инструментов MCP) оформляется в `core/orchestrator.py` с явными зависимостями в `clients`.

**Настройки.** `ORCH_*`: URLs зависимостей, `prompt_token_budget`, retries, `mock_mode`.

**Расширение.** Добавляя новые шаги пайплайна, обязательно описываем их в `schemas.py`, обновляем клиентов и покрываем `services/ai_orchestrator/tests` (юнит) + `tests/test_pipeline_integration.py` (E2E).

## LLM Service

**Назначение.** Инкапсулирует работу с LLM runtime и MCP tools. Управляет tool‑loop'ом и лимитами.

**API.**
- `POST /internal/llm/generate` — принимает `GenerateRequest` (режим, system prompt, messages, context_chunks, generation_params). Возвращает `GenerateResponse` с ответом, usage, списком tool call trace и meta.

**Взаимодействия.**
- LLM runtime (`llm_runtime_url`) — REST совместимый API (OpenAI‑style).
- MCP tools proxy (`mcp_proxy_url`) — выполняет инструменты, когда runtime возвращает `tool_call`.

**Настройки.** `LLM_SERVICE_*` (дефолтная модель, лимиты токенов/шагов, флаг JSON‑mode, mock режим).

**Расширение.** Новые режимы генерации добавляем в `core/orchestrator.py` (методы `_build_runtime_payload`, `_execute_tool`). Для каждого нового инструмента — описания в MCP proxy + тесты в `services/llm_service/tests`. Не забываем обновить документацию о параметрах API.

## MCP Tools Proxy

**Назначение.** Прозрачный прокси между LLM и корпоративными инструментами (по спецификации MCP). Следит за rate limits и безопасностью.

**API.**
- `POST /internal/mcp/execute` — принимает `MCPExecuteRequest` (название инструмента, аргументы, пользовательский контекст, trace). Возвращает `MCPExecuteResponse` (`status`, `result`, `metrics`).

**Настройки.** `MCP_PROXY_*`: лимиты по страницам, байтам, количеству вызовов, списки запрещенных ключевых слов.

**Расширение.** Новые инструменты регистрируются в `core/executor.py` + `tools/*`. Нужно описать в README и добавить тесты (`services/mcp_tools_proxy/tests`). Любые операции с файлами должны проходить аудит (см. `docs/mcp_tools_proxy_spec.md`).

## Document Service

**Назначение.** Отвечает за чтение метаданных документов, секций и обновление статусов после обработки. Сейчас используется in‑memory репозиторий, интерфейс максимально приближен к прод API.

**API.**
- `GET /internal/documents` — параметры фильтрации (`status`, `product`, `tag`, `search`), обязателен заголовок `X-Tenant-ID`.
- `GET /internal/documents/{doc_id}` — детальная карточка документа.
- `GET /internal/documents/{doc_id}/sections/{section_id}` — содержимое секции.
- `POST /internal/documents/status` — обновление статуса обработки (`StatusUpdateRequest`), используется ingestion pipeline.

**Настройки.** `DOC_*`: mock_mode, реквизиты БД/кэша (пока заглушки).

**Расширение.** План интеграции с реальной БД: реализовать репозиторий в `core/repository.py` (или заменить InMemory). Не забываем о мульти‑тенантной изоляции (`X-Tenant-ID`). Тесты — `services/document_service/tests/test_documents.py`.

## Ingestion Service

**Назначение.** Принимает загрузки от API Gateway, ставит их в очередь на обработку, обновляет статусы. Сейчас очередь in‑memory, но интерфейс повторяет production pipeline.

**API.**
- `POST /internal/ingestion/enqueue` — ожидает файл и заголовок `X-Tenant-ID`, возвращает `job_id`, `doc_id`, `status=queued`.
- `POST /internal/ingestion/status` — обновляет статус задания (`processing|failed|done`), используется воркерами.

**Настройки.** `INGEST_*`: `storage_path` (боевой каталог по умолчанию `/var/lib/visior_ingestion_storage`; в mock-режиме автоматически используется `/tmp/visior_ingestion_storage`), mock_mode.

**Расширение.** Для связи с реальной шиной (S3, SQS, Kafka) заменяем `core/storage.py` и обновляем тесты (`services/ingestion_service/tests`). При добавлении новых шагов пайплайна фиксируем новые статусы в схемах.

## Retrieval Service

**Назначение.** Поиск релевантных чанков по индексам (сейчас in‑memory список). Используется AI Orchestrator.

**API.**
- `POST /internal/retrieval/search` — принимает `RetrievalQuery` (`query`, `tenant_id`, `max_results`), возвращает `RetrievalResponse` с массивом `hits`.

**Настройки.** `RETR_*`: `max_results`, mock_mode.

**Расширение.** При подключении реальной векторной БД реализуем адаптер в `core/index.py`. Не изменяем форму `RetrievalResponse`, чтобы не нарушить контракты с оркестратором. Покрытие тестами — `services/retrieval_service/tests`.

## Интеграционные соглашения

1. **Трассировка.** `trace_id` передается от API Gateway → Orchestrator → LLM/Safety и обратно. При добавлении новых сервисов сохраняем trace_id в метаданных ответов.
2. **Аутентификация.** API Gateway единственная точка, которая проверяет токены. Все внутренние сервисы требуют `X-Tenant-ID` либо user context в payload.
3. **Соглашения по safety.** Input safety вызывается до всех дорогих операций. Output safety обязателен перед отдачей ответа пользователю. Новые сервисы не должны обходить эти уровни.
4. **Тестирование.** У каждого сервиса есть `run_tests.sh` (локальные юнит‑тесты). Полный regression выполняем `pytest` из корня (включает E2E `tests/test_pipeline_integration.py`). Перед мержем — обязательно.
5. **Расширение API.** Любое новое поле добавляем в `schemas.py`, синхронизируем документацию в `docs/*.md`, обновляем соответствующие клиенты. Публичные контрактные изменения требуют версии/feature flag.

## Как добавлять новые фичи

1. Решаем, в каком сервисе логика должна жить. Для внешних API — скорее `api_gateway`, для длинных процессов — профильный сервис.
2. Обновляем схемы и клиенты. Например, добавляя новый downstream вызов из API Gateway, сначала описываем клиент в `api_gateway/clients`, затем внедряем его через `dependencies`.
3. Пишем юнит‑тесты в каталоге соответствующего сервиса и (если меняется сквозной поток) обновляем/добавляем интеграционные тесты в `tests/`.
4. Обновляем эту документацию и профильные спецификации (`docs/*_spec.md`), чтобы новые команды знали про контракты.
5. Проверяем `pytest` и, при необходимости, `docker-compose up --build` для smoke‑тестов.

Следуя этому документу, можно безопасно расширять пайплайн Orion, не нарушая сквозные контракты между микросервисами.
