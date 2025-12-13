# AI Orchestrator — progress

## Что уже реализовано
- Публичный endpoint `/internal/orchestrator/respond` на FastAPI (`routers/orchestrator.py`, `main.py`), healthcheck `/health`.
- Основной класс `core/orchestrator.Orchestrator` собирает цепочку Retrieval → LLM → Output Safety и формирует `OrchestratorResponse` с answer, sources, safety, telemetry.
- Клиенты Retrieval/LLM/Safety с поддержкой `mock_mode` (возвращают статические данные без сетевых вызовов) (`clients/*.py`).
- Простая сборка контекста с обрезкой по токен-бюджету в `core/context_builder.py`.
- Схемы `OrchestratorRequest/Response` описаны в `schemas.py`; fallback построения user-context из `user_id/tenant_id` при отсутствии блока `user`.
- Базовый юнит-тест `tests/test_respond.py` проверяет mock-поток и телеметрию `trace_id`.

## Как это реализовано
- Конфигурация через `ORCH_*` (`config.py`): URLs зависимостей, стратегия, токен-бюджет контекста, ретраи, `mock_mode` (по умолчанию `true`).
- Пайплайн `respond`: валидирует user-context, вызывает Retrieval (`/internal/retrieval/search`), режет контекст под `prompt_token_budget` (4 символа = 1 токен), вызывает LLM (`/internal/llm/generate`), затем Safety output (`/internal/safety/output-check`). При статусе safety не `allowed|sanitized` возвращает 400 `OUTPUT_BLOCKED`.
- Телеметрия (`Telemetry`) включает `trace_id`, латентность retrieval/LLM, `tool_steps` из ответа LLM. Блок `safety` фиксируется как input=allowed (жёстко) и output=ответ Safety.
- Ретрай и fallback логика отсутствуют, но есть поле `retry_attempts` в конфиге (не используется).
- В mock-режиме Retrieval/LLM/Safety возвращают статические ответы; Orchestrator возвращает `answer`/`sources`/`telemetry` на их основе.

## Что осталось сделать / отклонения от ТЗ
- Нет маршрутизации стратегий (MCP, FAQ, деградации): `model_strategy` не влияет на поведение, пайплайн фиксирован на RAG.
- Отсутствуют ретраи/таймауты/фолбэки, описанные в ТЗ (`ORCH_MAX_LATENCY_MS`, `ORCH_MAX_TOOL_STEPS`, повтор Retrieval/LLM).
- Safety integration: ожидает `status in {allowed,sanitized}`, но формирует блок `safety.input="allowed"` независимо от реального input safety статуса, не пробрасывает ошибки/trace метаданные; `sanitized_answer` от safety не используется — ответ всегда `llm_result["answer"]`.
- Контекст билдер примитивен (обрезка по символам), нет дедупликации/приоритизации чанков и учёта токенов/ролей; не учитываются `channel`, `locale`, `conversation_id`.
- Наблюдаемость: нет метрик/трейсов/структурированных логов, упомянутых в ТЗ (`orch_stage_latency`, `orch_requests_total`, OTel).
- Защита/валидация: нет проверки `tenant_id` согласованности между входом/ответами retrieval, не обрабатываются ошибки формата downstream (кроме raise_for_status).
- Моки: структура ответа не включает `telemetry.tool_steps` при отсутствии meta в LLM ответе; нет гарантий на поля, если mock отключён и downstream меняется.
