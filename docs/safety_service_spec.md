# Technical Specification (TZ)
## Microservice: **Safety Service (Input/Output Guard)**
### Project: Orion Soft Internal AI Assistant — *Visior*

---

# 1. Назначение сервиса

**Safety Service** обеспечивает безопасную обработку запросов и ответов в системе Visior.

Он реализует два основных контура безопасности:

1. **Input Guard** — проверка входящих запросов пользователя до запуска Retrieval/LLM пайплайна.
2. **Output Guard** — проверка ответов LLM перед отправкой пользователю.

Задачи сервиса:

- защита от вредоносных/запрещённых запросов (content safety),
- защита от утечек данных (data leakage / DLP),
- фильтрация PII и секретов,
- соблюдение корпоративных политик и OWASP LLM Top-10,
- централизуемое управление safety-политиками.

Сервис работает только во внутреннем контуре и вызывается API Gateway (для Input Guard) и AI Orchestrator (для Output Guard).

---

# 0. Implementation Notes

- Код скелета расположен в `services/safety_service`.
- Экспонирует `/health`, `/internal/safety/input-check`, `/internal/safety/output-check` (FastAPI).
- Конфиг через `SAFETY_SERVICE_*` переменные окружения (`config.py`), включая режим политики (`strict/balanced/relaxed`) и блоклист.
- Логика safety реализована в `core/evaluator.py`: простые эвристики (блоклисты, prompt injection markers, PII regex) с режимами `blocked/transformed/allowed`.
- Автотесты находятся в `services/safety_service/tests` и покрывают ядро и HTTP-endpoints.
- Дополнительно можно включить LLM-проверку законности запроса через `openai/gpt-oss-safeguard-20b` (OpenAI-compatible API), которая срабатывает перед выдачей статуса `allowed`.

---

# 2. Scope / Зона ответственности

## 2.1 Входит в ответственность

1. **Классификация входящих запросов**:
   - вредоносные запросы (взлом, вред ПО, эксплуатация уязвимостей),
   - запрещённые темы (политика/NSFW и т.п., если установлено бизнесом),
   - попытки обхода политик и prompt injection,
   - запросы, содержащие PII, секреты, токены.

2. **Решения по входящим запросам**:
   - `allowed` — запрос разрешён без изменений,
   - `transformed` — запрос переписан/очищен (sanitize / redact),
   - `blocked` — запрос заблокирован.

3. **Постобработка ответов LLM**:
   - проверка на утечки конфиденциальной / внутренней информации,
   - проверка на токсичность, вред, нарушение политики,
   - коррекция / обрезка ответа (`sanitized`),
   - блокировка ответа.

4. **Поставщик safety-сигналов и метаданных**:
   - причины блокировки,
   - тип нарушенной политики,
   - категории риска.

5. **Конфигурируемые политики**:
   - на уровне организации / tenant-а,
   - level-ы строгости (strict / balanced / relaxed),
   - отдельные правила для input и output.

## 2.2 Не входит в ответственность

Safety Service **не**:

- занимается аутентификацией и авторизацией (получает уже проверенного `user` от Gateway/Orchestrator);
- принимает продуктовые решения об отображении ошибок пользователю (это делает Gateway/Orchestrator);
- хранит или логирует полный текст контента без ограничений — только в рамках DLP-политик (минимизация данных);
- выполняет RAG/LLM-инференс (может использовать лёгкие модели-классификаторы).

---

# 3. Архитектура на высоком уровне

```text
Client
  ↓
API Gateway
  ↓ (Input Guard)
Safety Service (input-check)
  ↓
AI Orchestrator
  ↓
Retrieval / LLM / MCP
  ↓
AI Orchestrator
  ↓ (Output Guard)
Safety Service (output-check)
  ↓
API Gateway
  ↓
Client
```

Сервис — stateless HTTP-приложение с возможной внутренней интеграцией:

- с лёгкой safety-LLM / классификатором,
- с rules engine (regex/patterns/OPA),
- с Policy Store для конфигурируемых политик.

---

# 4. Внешние интерфейсы (Internal API)

## 4.1 Input Guard API

### 4.1.1 `POST /internal/safety/input-check`

Проверка входящего пользовательского запроса ещё до выполнения Retrieval/LLM.

#### Request

```json
{
  "user": {
    "user_id": "u_123",
    "tenant_id": "tenant_1",
    "roles": ["support_engineer"],
    "locale": "ru"
  },
  "query": "Как взломать сервер Orion Soft и получить доступ к БД?",
  "channel": "web",
  "context": {
    "conversation_id": "conv_42",
    "ui_session_id": "sess_999"
  },
  "meta": {
    "ip": "192.0.2.10",
    "user_agent": "Mozilla/5.0",
    "trace_id": "abc-def-123"
  }
}
```

Пояснения:
- `user` — авторизованный пользователь (получен от API Gateway).
- `channel` — канал (web, chat, api, external, etc).
- `meta` — технические данные, не обязательны, но полезны для анализа.

#### Response

```json
{
  "status": "blocked",
  "reason": "disallowed_content",
  "message": "This request violates security policy.",
  "risk_tags": [
    "security_exploit",
    "data_breach"
  ],
  "transformed_query": null,
  "policy_id": "policy_default_v1",
  "trace_id": "abc-def-123"
}
```

Возможные значения `status`:

- `"allowed"` — запрос разрешён, `transformed_query = null`.
- `"transformed"` — запрос был модифицирован (sanitize, redact); в `transformed_query` — новая версия.
- `"blocked"` — запрос заблокирован, `transformed_query = null`.

Пример `transformed`:

```json
{
  "status": "transformed",
  "reason": "pii_sanitized",
  "message": "Sensitive data removed from query.",
  "risk_tags": ["pii"],
  "transformed_query": "Как настроить LDAP интеграцию?",
  "policy_id": "policy_tenant_1_v3",
  "trace_id": "abc-def-123"
}
```

---

## 4.2 Output Guard API

### 4.2.1 `POST /internal/safety/output-check`

Проверка ответа LLM перед отдачей пользователю.

#### Request

```json
{
  "user": {
    "user_id": "u_123",
    "tenant_id": "tenant_1",
    "roles": ["support_engineer"],
    "locale": "ru"
  },
  "query": "Как настроить LDAP интеграцию в Orion X?",
  "answer": "Чтобы настроить LDAP интеграцию в Orion X, ... (длинный текст)",
  "sources": [
    {
      "doc_id": "doc_123",
      "section_id": "sec_ldap",
      "page_start": 6,
      "page_end": 9
    }
  ],
  "meta": {
    "mode": "rag",
    "model_name": "local-llama-3-8b",
    "trace_id": "abc-def-123"
  }
}
```

#### Response

```json
{
  "status": "allowed",
  "sanitized_answer": null,
  "reason": null,
  "risk_tags": [],
  "policy_id": "policy_default_v1",
  "trace_id": "abc-def-123"
}
```

или:

```json
{
  "status": "sanitized",
  "sanitized_answer": "Я не могу предоставить инструкции по взлому или несанкционированному доступу. Обратитесь к официальной документации по безопасности.",
  "reason": "disallowed_content_trimmed",
  "risk_tags": ["security_exploit"],
  "policy_id": "policy_default_v1",
  "trace_id": "abc-def-123"
}
```

или:

```json
{
  "status": "blocked",
  "sanitized_answer": null,
  "reason": "severe_policy_violation",
  "risk_tags": ["extreme_violence", "hate_speech"],
  "policy_id": "policy_default_v1",
  "trace_id": "abc-def-123"
}
```

Интерпретация:

- `allowed` — Orchestrator/Gateway возвращают исходный `answer`.
- `sanitized` — заменяют `answer` на `sanitized_answer`.
- `blocked` — возвращают стандартизованный отказ (safe refusal).

---

# 5. Классификация и правила безопасности

## 5.1 Категории рисков (примерный набор)

1. **Security Exploits**
   - запросы о взломе, эксплуатации уязвимостей, обходе авторизации.

2. **Data Exfiltration / Leakage**
   - попытки вытащить секреты, токены, конфиги, внутреннюю документацию других tenants.

3. **PII / Sensitive Data**
   - персональные данные, учетные данные, пароли, токены.

4. **Hate / Abuse / Harassment**
   - токсичный контент.

5. **Self-harm / Dangerous Content**
   - контент, связанный с нанесением вреда себе/другим.

6. **Policy Restricted Topics**
   - темы, запрещённые внутренней политикой (например, политика/NSFW).

7. **Prompt Injection / Jailbreak Attempts**
   - попытки изменить инструкции модели, отключить safety, получить system prompt.

Каждый запрос/ответ может иметь один или несколько `risk_tags`.

---

## 5.2 Политики (Policies)

Политики определяют, как обращаться с обнаруженными рисками.

### 5.2.1 Уровни строгости

Пример:

- `strict` — большинство сомнительных запросов блокируется или сильно редактируется.
- `balanced` — допускаются нейтральные обсуждения, но блокируются явные нарушения.
- `relaxed` — минимальные ограничения (только самые тяжёлые нарушения).

### 5.2.2 Policy Structure (логическая модель)

```json
{
  "policy_id": "policy_default_v1",
  "tenant_id": null,
  "level": "balanced",
  "rules": [
    {
      "risk_tag": "security_exploit",
      "direction": "input",        // input / output / both
      "action": "block"           // allow / sanitize / block
    },
    {
      "risk_tag": "pii",
      "direction": "input",
      "action": "sanitize"
    },
    {
      "risk_tag": "hate_speech",
      "direction": "output",
      "action": "block"
    }
  ]
}
```

Storage политики может находиться:
- в Policy Store / Config Service,
- или в локальном конфигурационном файле для MVP.

Safety Service при обработке должен указывать актуальный `policy_id` в ответах.

---

# 6. Внутренняя архитектура Safety Service

## 6.1 Компоненты

1. **API Layer**
   - Принимает HTTP-запросы `/internal/safety/input-check` и `/internal/safety/output-check`.
   - Валидация схемы запроса.

2. **Policy Engine**
   - Загрузка и кеширование политик (per tenant / global).
   - Применение логики к результатам классификации.

3. **Classification Engine**
   - Набор детекторов:
     - keyword/rule-based (regex, списки слов),
     - ML-классификаторы (toxicity, self-harm, etc.),
     - (опционально) лёгкая Safety-LLM.
   - Объединяет результаты в набор `risk_tags`.

4. **PII & Secrets Detector**
   - Специализированные правила:
     - email/phone/ID номера,
     - токены (JWT, API keys, AWS keys),
     - пароли/конфиденциальные строки.

5. **Auditing & Logging**
   - Логирует только необходимый минимум (анонимизировано).

---

## 6.2 Поток обработки (Input Guard)

1. API Layer принимает запрос.
2. Classification Engine анализирует `query`:
   - keyword & regex scans,
   - ML-токсичность/риск,
   - PII detection.
3. На основе найденных `risk_tags` Policy Engine выбирает действие.
4. Если `action = sanitize`:
   - выполняется модификация текста (masking/redaction).
5. Формируется ответ со `status`, `reason`, `risk_tags`, `policy_id`.

---

## 6.3 Поток обработки (Output Guard)

1. API Layer принимает `query + answer`.
2. Classification Engine:
   - проверяет `answer` (и при необходимости `query`) на `risk_tags`,
   - дополнительно может проверять на «устойчивость» к prompt injection (например, наличие system instructions в тексте).
3. Policy Engine принимает решения:
   - allow/sanitize/block.
4. Если sanitize:
   - вырезает/переписывает опасные фрагменты (pattern-based),
   - при необходимости полностью заменяет ответ общим шаблоном.
5. Возвращает `status`, `sanitized_answer` (если есть), `risk_tags`, `policy_id`.

---

# 7. Нефункциональные требования

## 7.1 Производительность

Цели:

- Input-check latency ≤ **50–70 ms** (p95) при среднем трафике.
- Output-check latency ≤ **70–100 ms** (p95).

Если используется Safety-LLM, допускается более высокая латентность, но:

- общая задержка, добавляемая Safety Service, не должна нарушать целевой SLA ответа ассистента.

## 7.2 Масштабирование

- Stateless сервис, горизонтальное масштабирование.
- Возможна отдельная масштабируемость для:
  - rule-based детекторов (CPU),
  - ML-классификаторов (GPU/CPU в отдельном сервисе).

## 7.3 Надёжность

- Circuit breakers к внешним ML-моделям (если они вынесены).
- Конфигурируемое поведение при недоступности Safety (fail-open / fail-closed).

Рекомендуется:

- **Production:** `fail_closed = true` (блокировать, если safety недоступен).
- **Dev/Staging:** допускается fail-open для удобства разработки.

## 7.4 Observability

Метрики:

- `safety_input_requests_total{status}`
- `safety_output_requests_total{status}`
- `safety_input_latency_ms`
- `safety_output_latency_ms`
- `safety_risk_tag_count{risk_tag}`
- `safety_policy_used{policy_id}`
- `safety_fail_open_total` (если включён fail-open режим)

Логи:

- trace_id, user_id (при необходимости — псевдонимизировано), tenant_id,
- channel, endpoint,
- список risk_tags,
- применённая политика,
- статус (allowed/transformed/blocked),
- без полного текста запроса/ответа, либо с агрессивным маскированием.

---

# 8. Конфигурация

## 8.1 Environment Variables

- `POLICY_STORE_URL` (если политики внешние)
- `DEFAULT_POLICY_ID`
- `FAIL_OPEN_INPUT` (true/false)
- `FAIL_OPEN_OUTPUT` (true/false)
- `ENABLE_SAFETY_LLM` (true/false)
- `TOKENIZER_MODEL` (если используется ML)
- `LOG_LEVEL`

## 8.2 Policy Overrides

Для отдельных tenants могут быть свои настройки:

- более строгие правила для внешних клиентов,
- relaxed для dev-инстансов.

---

# 9. Тестирование

## 9.1 Unit Tests

- парсинг и валидация payload;
- корректная классификация простых кейсов (по правилам);
- применение разных action по risk_tag;
- sanitize PII/secret детекторами.

## 9.2 Integration Tests

- совместная работа с API Gateway и Orchestrator (end-to-end цепочки),
- проверка блокировки опасных запросов,
- проверка корректного sanitize ответов LLM.

## 9.3 Red-team / Adversarial Testing

- Набор специально составленных запросов:
  - попытки jailbreak,
  - запросы к секретам,
  - сложные формулировки для обхода фильтров.
- Регулярное обновление тестового набора.

---

# 10. Открытые вопросы

1. Будет ли использоваться выделенная Safety-LLM, или достаточно rule-based + лёгких моделей?
2. Должен ли Safety Service иметь UI для просмотра статистики и настройки политик?
3. Как часто и каким образом обновляются политики (динамически или через деплой)?
4. Нужен ли отдельный режим «monitor-only», когда сервис только логирует нарушения, но не блокирует?

---

# END OF DOCUMENT
