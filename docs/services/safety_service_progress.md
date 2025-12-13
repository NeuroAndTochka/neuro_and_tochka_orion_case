# Safety Service — progress

## Что уже реализовано
- Внешние endpoint'ы `/internal/safety/input-check`, `/internal/safety/output-check` и `/health` подняты на FastAPI (`safety_service/main.py`, `routers/safety.py`).
- Схемы запросов/ответов описаны в `safety_service/schemas.py` (`SafetyResponse` с `status/reason/policy_id/trace_id`, поддержка `transformed_query`/`transformed_answer`).
- Конфигурация через `SAFETY_SERVICE_*`: политика (`policy_mode`), блоклист, флаг санитайза PII, `default_policy_id`, лог‑уровень (`config.py`).
- Правила input/output guard реализованы в `core/evaluator.py`: блоклист, prompt injection маркеры, PII‑regex, простые data‑leak ключевые слова; статус `allowed|blocked|transformed`.
- Базовые автотесты покрывают HTTP endpoints и основные ветки эвристик (`services/safety_service/tests/test_api.py`, `test_evaluator.py`).

## Как это реализовано
- Input-check: `evaluate_input` проверяет блоклист (`security_exploit` risk_tag), prompt injection (`prompt_injection`), затем PII. Для PII действие зависит от `policy_mode` (`strict` блокирует, `balanced` трансформирует при `enable_pii_sanitize=True`, `relaxed` пропускает). `trace_id` берётся из `meta.trace_id` либо генерируется, `policy_id` — `default_policy_id`.
- Output-check: `evaluate_output` сперва ищет запрещённые ключевые слова в answer (`disallowed_content`), затем `data leak` маркеры (`confidential/internal use/...`) с опциональным редактированием, затем PII. При санитайзе пишет в `transformed_answer`, статус `transformed`, иначе `blocked`/`allowed`. `query/sources/context` не участвуют в решении.
- PII детекторы: regex для email, телефонов, карт/SSN‑подобных номеров; замена на `[REDACTED]` при санитайзе. Prompt injection маркеры жёстко заданы (`ignore previous`, `disregard`, `override`, `system prompt`).
- Логирование на structlog настраивается в `logging.py`, но в коде правил/роутов явного логирования/метрик нет.

## Что осталось сделать / отклонения от ТЗ
- Нет режима `monitor` или fail-open/fail-closed настроек, упомянутых в ТЗ; реакция фиксирована на `allowed|blocked|transformed` без мягкого мониторинга.
- Не реализован mock-режим/статические ответы, описанные в документации; сервис всегда исполняет реальные эвристики.
- Ограниченный набор детекторов: нет токсичности/hate/self-harm, секретов (API keys/JWT), систем prompt leakage и др.; policy engine отсутствует (нет per-tenant политик или внешнего Policy Store), действия жёстко зашиты.
- Output-check игнорирует `query`, `sources`, `context` и meta поля кроме `trace_id`; data leak проверка ограничена списком ключевых слов.
- Спецификацию по наблюдаемости (метрики `safety_*`, audit логирование risk_tags/policy_id) не реализовали.
