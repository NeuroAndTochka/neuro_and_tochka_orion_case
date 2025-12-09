# Technical Specification (TZ)
## Microservice: **AI Orchestrator**
### Project: Orion Soft Internal AI Assistant — *Visior*

---

# 1. Назначение сервиса

AI Orchestrator — центральный координационный слой, который принимает запросы от API Gateway (после прохождения Input Safety), управляет полным пайплайном RAG/MCP и подготавливает ответ для LLM Service и последующих слоёв. Он решает, какую стратегию выбрать (прямой вызов LLM, RAG, MCP, поиск дополнительных данных), собирает телеметрию и обеспечивает единый интерфейс для фронта/интеграций.

---

# 2. Область ответственности

## 2.1 Входит в ответственность

1. **Роутинг режимов**: выбор между RAG, MCP-assisted, Q&A по шаблонам, режимом "FAQ" либо эскалацией к человеку.
2. **Управление пайплайном**: последовательный вызов Retrieval Service, LLM Service, Safety Service (output), формирование ответа.
3. **Context Builder orchestration**: запрос чанков у Retrieval, дедупликация, подбор по токен-бюджету, подготовка контекста для LLM.
4. **Tool policy**: включение/выключение MCP инструментов в зависимости от роли пользователя, уровня доверия, tenant-политик.
5. **Метрики и логирование**: сбор trace_id, latency per stage, количество tool steps, статистика safety блокировок.
6. **Fallback сценарии**: повторный запрос к Retrieval, смена модели, деградация на короткий ответ в случае таймаутов.

## 2.2 Не входит в ответственность

- Выполнение самих LLM-инференсов (это LLM Service).
- Ингеренция документов (Ingestion Service).
- Проверка аутентификации (API Gateway).
- Хранение истории диалогов.

---

# 3. Архитектура (High-level)

```
Client → API Gateway → AI Orchestrator
                       ├─ Retrieval Service (doc/section/chunk)
                       ├─ LLM Service (RAG + MCP)
                       ├─ Safety Service (output)
                       └─ Observability stack (metrics/logs)
```

Сервис stateless, горизонтально масштабируемый (Kubernetes Deployment). Все вызовы сопровождаются `trace_id`, который прокидывается вниз.

---

# 4. Внешний API

## 4.1 `POST /internal/orchestrator/respond`

**Request**
```json
{
  "conversation_id": "conv_123",
  "user": {
    "user_id": "u_1",
    "tenant_id": "tenant_1",
    "roles": ["support"]
  },
  "query": "Как настроить LDAP интеграцию?",
  "channel": "web",
  "locale": "ru",
  "trace_id": "abc-def-123"
}
```

**Response (успех)**
```json
{
  "answer": "Чтобы настроить LDAP...",
  "sources": [...],
  "safety": {
    "input": "allowed",
    "output": "allowed"
  },
  "telemetry": {
    "trace_id": "abc-def-123",
    "retrieval_latency_ms": 180,
    "llm_latency_ms": 920,
    "tool_steps": 1
  }
}
```

**Response (ошибка)**
```json
{
  "error": {
    "code": "PIPELINE_TIMEOUT",
    "message": "LLM не успел ответить за 3 секунды"
  },
  "trace_id": "abc-def-123"
}
```

---

# 5. Основной поток работы

1. Получить запрос от API Gateway, проверить `trace_id`, user context.
2. Вызвать Retrieval Service (`/internal/retrieval/search`) с параметрами пользователя и вопросом.
3. Применить стратегию Context Builder: обрезать чанки до `MAX_PROMPT_TOKENS`, добавить метаданные.
4. Сформировать payload для LLM Service (`/internal/llm/generate`), включая system_prompt и разрешённые инструменты.
5. Дождаться ответа LLM Service. При необходимости повторить вызов с другим режимом (fallback) максимум 1 раз.
6. Отправить ответ в Output Safety (`/internal/safety/output-check`) с информацией о пользователе, вопросе и черновиком ответа.
7. Сформировать итоговую структуру ответа (answer + sources + telemetry) и вернуть наверх.
8. Проложить события в лог/метрики.

---

# 6. Интеграции и контракты

| Сервис           | Endpoint                          | Назначение                      |
|------------------|-----------------------------------|---------------------------------|
| Retrieval        | `/internal/retrieval/search`      | Получение doc/section/chunk     |
| LLM Service      | `/internal/llm/generate`          | Генерация ответа с MCP          |
| Safety Service   | `/internal/safety/output-check`   | Финальная проверка ответа       |
| Observability    | `/internal/metrics` (push)        | Публикация метрик/трейсов       |

Все вызовы содержат `X-Request-ID`, `X-Tenant-ID`, `Authorization` (service-to-service token).

---

# 7. Конфигурация (ENV)

| Переменная                     | Назначение                              |
|--------------------------------|------------------------------------------|
| `ORCH_RETRIEVAL_URL`           | Базовый URL Retrieval Service            |
| `ORCH_LLM_URL`                 | URL LLM Service                          |
| `ORCH_SAFETY_URL`              | URL Safety Service (output)              |
| `ORCH_MODEL_STRATEGY`          | Режим (например, `rag_default`)          |
| `ORCH_MAX_LATENCY_MS`          | Общий таймаут пайплайна                  |
| `ORCH_MAX_TOOL_STEPS`          | Максимум MCP шагов, разрешённых от LLM   |
| `ORCH_PROMPT_TOKEN_BUDGET`     | Ограничение на суммарный контекст        |
| `ORCH_RETRY_ATTEMPTS`          | Число повторов при ошибках               |
| `LOG_LEVEL`                    | Уровень логирования                      |
| `ENABLE_TRACE_EXPORT`          | Включить экспорт в Jaeger/OTel           |

---

# 8. Error handling & Fallbacks

- **Retrieval timeout** → возврат `ERROR_RETRIEVAL_TIMEOUT`, попытка снова 1 раз.
- **LLM runtime error** → переключение на альтернативную модель (если конфигурирована) или возврат `LLM_RUNTIME_ERROR`.
- **Safety блокировка** → передача кода `OUTPUT_BLOCKED` в API Gateway.
- **Tool loop / limit exceeded** → прерывание и сообщение пользователю о невозможности ответить.

---

# 9. Наблюдаемость

Метрики (Prometheus):
- `orch_requests_total{mode=...,tenant=...}`
- `orch_stage_latency_ms{stage=retrieval|llm|safety}`
- `orch_tool_steps_histogram`
- `orch_failures_total{code=...}`

Логи (structured): trace_id, stage, latency, количество чанков, model_name.

Трейсы (OpenTelemetry): спаны на Retrieval, LLM, Safety.

---

# 10. Тестирование

## Unit
- Построение payload для LLM.
- Обработка ответа Retrieval (селекция чанков).
- Правила fallback по конфигурации.

## Integration
- e2e сценарий с mock Retrieval + LLM + Safety.
- Проверка таймаутов и повторов.

## Load / Chaos
- Тесты с высоким количеством параллельных запросов.
- Инжекция ошибок (LLM timeout, Safety error).

---

# 11. Security & Governance

- Все запросы подписаны service token + mutual TLS (в будущем).
- Tenant isolation: сверка `tenant_id` на каждом шаге.
- Логи не содержат PII/секретов.
- Соблюдение OWASP LLM-Top10 посредством двух safety контуров и MCP-guarded tool use.

---

# 12. Открытые вопросы

1. Нужен ли stateful режим (кэш контекста) для ускорения многотуровых сессий?
2. Следует ли реализовать адаптивный выбор Retrieval стека (dense only vs hybrid)?
3. Поддерживать ли streaming в сторону API Gateway?

---

# 13. Итог

AI Orchestrator обеспечивает управляемость пайплайна, сохраняя при этом модульность и расширяемость. Чёткие интерфейсы с Retrieval, LLM и Safety позволяют добавлять новые режимы, модели и политики без изменения фронтенда.
