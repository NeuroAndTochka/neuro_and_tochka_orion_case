# Техническая спецификация — Safety Service

## 1. Назначение
Rule-based input/output guard для ассистента. Проверяет ключевые слова, простые PII и признаки prompt injection; может редактировать ответ/запрос либо блокировать его. Работает как внутренний сервис без внешних моделей.

## 2. API (`/internal/safety`)
- `POST /input-check`
  - Request: `user{user_id,tenant_id,roles?,locale?}`, `query`, опц. `channel`, `context{conversation_id?,ui_session_id?}`, `meta{ip?,user_agent?,trace_id?}`.
  - Response: `SafetyResponse` (`status: allowed|transformed|blocked`, `reason`, `message`, `risk_tags[]`, `transformed_query?`, `policy_id`, `trace_id`).
- `POST /output-check`
  - Request: `user`, `query`, `answer`, опц. `sources[{doc_id?,section_id?,page_start?,page_end?}]`, `meta`, `context`.
  - Response: `SafetyResponse` (может содержать `transformed_answer`).
- `/health` — `{"status":"ok"}`.

## 3. Логика
- Блокирует при наличии слов из `blocklist`.
- Prompt injection: простые маркеры (`ignore previous`, `disregard`, `override`, `system prompt`).
- PII: e-mail, телефон, номера карт/SSN-формата. Действие зависит от `policy_mode`:
  - `strict` → блокировка;
  - `balanced` (default) → `transformed` с редактированием, если `enable_pii_sanitize=true`;
  - `relaxed` → пропускает.
- Output-check дополнительно помечает утечки (`confidential`, `token`, `api key` и т.п.) и при включённом sanitize редактирует ответ.

## 4. Конфигурация (`SAFETY_SERVICE_*`)
`app_name`, `host/port/log_level`, `policy_mode`, `blocklist` (list[str]), `enable_pii_sanitize`, `default_policy_id`.

## 5. Тестирование
Юнит-тесты в `services/safety_service/tests` проверяют блоклист, PII и поведение `policy_mode`. Сервис stateless; дополнительных интеграционных тестов не требуется.
