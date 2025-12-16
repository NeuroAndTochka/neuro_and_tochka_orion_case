# Safety Service

## Назначение
Rule-based input/output guard. Проверяет блоклист, простые признаки prompt injection и PII; умеет редактировать PII в зависимости от режима политики.

## Эндпоинты (`/internal/safety`)
- `POST /input-check` — поля `user`, `query`, опц. `channel`, `context`, `meta(trace_id?)`. Возвращает `SafetyResponse` со статусом `allowed|transformed|blocked`, `risk_tags`, `transformed_query?`, `policy_id`, `trace_id`.
- `POST /output-check` — `user`, `query`, `answer`, опц. `sources`, `meta`, `context`. Может вернуть `transformed_answer` или заблокировать ответ.
- `GET /health` — `{"status":"ok"}` (через приложение).

## Логика
- Блокирует запрос, если встречается слово из `blocklist` или маркеры prompt injection.
- PII: редактирует/блокирует в зависимости от `policy_mode` (`strict|balanced|relaxed`) и `enable_pii_sanitize`.
- Output-check также помечает потенциальную утечку по ключевым словам (`confidential`, `token` и т.п.).

## Конфигурация (`SAFETY_SERVICE_*`)
`policy_mode`, `blocklist` (список слов), `enable_pii_sanitize`, `default_policy_id`, `host/port/log_level`.

## Примечания
- Сервис stateless; не использует внешние модели.
- Ответ всегда содержит `trace_id` (генерируется, если не пришёл в meta).
