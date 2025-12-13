# Orion SaaS Readiness — Progress Snapshot

Оценка готовности к прод-внедрению для всех микросервисов. Проценты — субъективный показатель «production readiness» с учётом полноты функций по ТЗ, отсутствия критичных дыр (auth/тенантность/лимиты), наблюдаемости и эксплуатационной готовности.

## Методика
- **Функционал**: соответствие описанным контрактам/режимам.
- **Надёжность/безопасность**: auth, тенантность, rate limiting, fail-open/closed, валидации.
- **Наблюдаемость**: метрики, логирование, трассировка, health.
- **Интеграции**: внешние зависимости, моки vs реальные клиенты.
- **Тесты**: покрытие unit/e2e, mock-режимы.

## Сводка по сервисам
| Сервис | Readiness | Реализовано | Ключевые пробелы |
| --- | --- | --- | --- |
| API Gateway | ~65% | Все публичные ручки, auth+rate limit, safety→orch цепочка, mock-mode, базовые тесты | Доклиент ходит на `/internal/documents/list` (404), upload не возвращает `job_id`, rate limit per-endpoint, auth fallback без introspection, нет метрик |
| Safety Service | ~50% | Input/output guard (блоклист, PII, prompt-injection), конфиг, тесты | Нет monitor/fail-open, mock режима, расширенных детекторов/пер-tenant политик, метрик/аудита; output-check не использует query/sources |
| AI Orchestrator | ~50% | `/respond`, Retrieval→LLM→Safety цепочка, mock-клиенты, контекст-билдер, тест | Нет стратегий/фолбэков/ретраев, sanitized_answer не используется, примитивный контекст, нет метрик/валидаторов tenant |
| LLM Service | ~55% | `/generate`, tool-loop MCP, mock runtime/MCP, промпт-билдер, тесты | Нет контроля токен-бюджета/таймаутов/ретраев, user для MCP захардкожен, `mode`/json_mode не управляют поведением, нет метрик/latency, обработка лимитов tool-loop слабая |
| MCP Tools Proxy | ~55% | Реестр инструментов чтения/поиска, tenant-check, rate limiter, конфиг, тесты | Blocklist не применяется, лимит без окна, mock_mode без стат. ответов/метрик, нет ролей/наблюдаемости |
| Document Service | ~70% | CRUD документов/секций/status/download-url, tenant isolation на чтение, S3/local storage, SQLite+Postgres тесты | Нет auth/caches/метрик, status/create без строгого tenant/валидации статусов, нет версионности, поиск ограничен |
| Ingestion Service | ~55% | enqueue/status, JobStore+очередь, pipeline парсинг→embedding→summary→doc service→vector store, конфиг, тесты | Нет API для job/log/config/tree, нет ретраев/внешнего брокера, слабая валидация/tenant для status, нет метрик/трасс, mock_mode не выключает внешние вызовы |
| Retrieval Service | ~45% | `/search`+health, mock индекс, ChromaIndex с фильтрами, конфиг, max_results cap, тест | Tenant не enforce в роуте/mock, mock не применяет фильтры/topk/min_score, нет метрик/таймаутов/многоуровневого поиска, auth/X-Request-ID отсутствуют |
| ML Observer | ~40% | Experiments/runs/documents CRUD, mock retrieval/LLM, прокси ingestion/doc, UI, конфиг, тесты | Retrieval/LLM mock, MinIO/артефакты не используются, нет auth (только allowed_tenant), нет метрик/health зависимостей/retry, UI открыт |

## Общая оценка
- **Совокупная готовность**: ~55% до SaaS-внедрения. Базовый happy-path работает в mock режиме, есть e2e тест ассистента, но не хватает production-защит (auth, метрики, тенантность, ретраи, документация контрактов).
- **Кросс-сервисные разрывы**: отсутствие единой аутентификации service-to-service, метрик/трейсов, единообразных rate limits и валидации tenant_id. Mock режимы часто не закрывают все зависимости.

## Ближайшие приоритеты для прод
1. Безопасность и контракты: жёсткая auth/tenancy во всех ручках, корректный DocumentClient в Gateway, fail-open/closed safety.
2. Наблюдаемость: метрики/трейсы для gateway/safety/orchestrator/llm/ingestion/retrieval, health checks зависимостей.
3. Надёжность: ретраи/таймауты и пер-tenant rate limits, batch/status в ingestion, корректная обработка sanitized_answer.
4. Поиск/данные: доработать Retrieval (тенантный фильтр, topk_per_doc, min_score, многоуровневый поиск), включить vector store/embedding в ingestion.
5. Хранилища и конфиг: требовать Postgres/S3 для prod режимов, завершить версионность документов и статусные машины.
