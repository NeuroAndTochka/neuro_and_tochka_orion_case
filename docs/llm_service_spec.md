# Technical Specification (TZ)
## Microservice: **LLM Service (RAG + MCP Orchestration Layer)**
### Project: Orion Soft Internal AI Assistant — *Visior*

---

# 1. Назначение сервиса

**LLM Service** — микросервис, выполняющий:

- низкоуровневое взаимодействие с моделью (local vLLM / remote OpenAI-compatible server),
- построение RAG-инференса на основе контекста,
- обработку tool-calls (MCP) от модели,
- управление шагами генерации (multi-turn tool reasoning),
- предоставление согласованного интерфейса для AI Orchestrator,
- формирование структурированного ответа (answer, tokens, tool trace).

LLM Service скрывает сложность взаимодействия с моделью, обеспечивая безопасный, контролируемый и воспроизводимый способ генерации.

---

# 0. Implementation Notes

- Скелет сервиса: `services/llm_service` (FastAPI + httpx).
- Endpoint: `POST /internal/llm/generate` + `/health`.
- Основной поток реализован в `core/orchestrator.py` (prompt сборка, вызов LLM runtime, MCP loop, ограничение шагов).
- LLM runtime и MCP proxy абстрагированы клиентами (`clients/runtime.py`, `clients/mcp.py`); в mock-режиме имитируют ответы.
- Конфигурация через `LLM_SERVICE_*` переменные (`config.py`), поддерживаются лимиты токенов, шагов, JSON-mode.
- Юнит-тесты в `services/llm_service/tests` проверяют базовый ответ и tool-loop.

---

# 2. Scope / Зона ответственности

## 2.1 Входит в ответственность

1. **Inference** — запуск модели LLM:
   - chat completion,
   - rag-mode completion,
   - deterministic / temperature-controlled generation.

2. **RAG Integration** — включение context_chunks:
   - добавление в prompt,
   - токенизация и подсчёт бюджета,
   - trimming / merging чанков при необходимости.

3. **MCP Tool Orchestration** — управляет тем, как LLM вызывает инструменты:
   - принимает tool-call от модели,
   - вызывает **MCP Tools Proxy**,
   - подаёт результат обратно в модель как очередное сообщение,
   - поддерживает циклическое выполнение до лимита шагов.

4. **Prompt Assembly** — формирование:
   - system_prompt,
   - user/assistant/previous messages,
   - retrieval context block,
   - специального MCP instructions блока.

5. **Token & Time Control**
   - token-limit enforcement,
   - watchdog timeout (ограничение времени генерации),
   - попытки повторной генерации (retry).

6. **Model Safety Guardrails (internal)**
   - защита от runaway loops,
   - ограничение количества tool-calls,
   - контроль размера промежуточных ответов.

## 2.2 Не входит в ответственность

- safety-фильтрация (это Safety Service),
- retrieval (это Retrieval Service),
- хранение документов,
- управление пользователями и авторизацией,
- долгосрочное хранение истории диалогов.

---

# 3. Архитектура (High-level)

```text
AI Orchestrator
   ↓
LLM Service
   ├─ Local/Remote LLM Runtime (vLLM / OpenAI-compatible)
   ├─ MCP Tools Proxy (tool-calls)
   ├─ Token/Context Manager
   ├─ Prompt Builder
   └─ Safety-internal protections (loop/overuse guards)
```

LLM Service — stateless.
Оркестрация multi-step reasoning осуществляется внутри сервиса или при поддержке vLLM/OpenAI-compatible JSON-mode.

---

# 4. External API (Internal Interface)

## 4.1 Основной эндпоинт

### `POST /internal/llm/generate`

#### Request

```json
{
  "mode": "rag",
  "system_prompt": "You are Visior, the internal AI assistant...",
  "messages": [
    { "role": "user", "content": "Как настроить LDAP интеграцию?" }
  ],
  "context_chunks": [
    {
      "doc_id": "doc_123",
      "section_id": "sec_ldap",
      "text": "Для настройки LDAP интеграции...",
      "page_start": 6,
      "page_end": 7
    }
  ],
  "generation_params": {
    "max_tokens": 512,
    "temperature": 0.2,
    "top_p": 0.95,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "stop": ["</answer>"]
  },
  "trace_id": "abc-def-123"
}
```

#### Response

```json
{
  "answer": "Чтобы настроить LDAP интеграцию в Orion X, выполните...",
  "used_tokens": {
    "prompt": 1180,
    "completion": 210
  },
  "tools_called": [
    {
      "name": "read_doc_section",
      "arguments": { "doc_id": "doc_123", "page_start": 6, "page_end": 7 },
      "result_summary": "LLM requested additional page range 6–7"
    }
  ],
  "meta": {
    "model_name": "local-llama-3-8b",
    "latency_ms": 950,
    "tool_steps": 1,
    "trace_id": "abc-def-123"
  }
}
```

---

# 5. Core Logic

## 5.1 Prompt Structure

В зависимости от режима RAG формируется такой prompt:

```
[SYSTEM PROMPT]

[CONTEXT HEADER: "Below are relevant sections from Orion documentation..."]
<context chunk 1>
<context chunk 2>
...

[USER MESSAGE]
```

При MCP включается:

```
[INSTRUCTIONS FOR TOOL USE]
You may use the following tools:
- read_doc_section
- read_doc_pages
...
Return tool calls in JSON format:
{"tool_name": "...", "arguments": {...}}
```

---

# 6. Tool-Call Orchestration (MCP loop)

LLM Service управляет циклом reasoning:

### Алгоритм:

1. Вызвать модель с текущими сообщениями.
2. Если модель отвечает обычным текстом → завершить.
3. Если модель генерирует MCP tool-call JSON →
   - валидировать структуру,
   - вызвать MCP Tools Proxy,
   - добавить ответ MCP как `assistant` message,
   - продолжить генерацию (переход к шагу 1).
4. Остановиться по одному из условий:
   - модель вернула финальный текст,
   - превышено количество tool-calls,
   - превышен token-budget,
   - превысили timeout.

### Пример tool-call потока:

```
assistant:
  {"tool_name": "read_doc_section", "arguments": {"doc_id": "doc_123", "section_id": "sec_ldap"}}

LLM Service → MCP Proxy → returns section text

LLM Service adds:
assistant:
  {"tool_result": "...section text...", "tool_name": "read_doc_section"}

LLM generates final answer.
```

---

# 7. Token Management

LLM Service должен:

- оценивать токенизацию входящих сообщений,
- корректировать контекст (если слишком большое),
- следить за cumulative tokens (включая tool-calls),
- останавливать reasoning при превышении лимитов.

Типичные ограничения:

- `max_prompt_tokens ≈ 4k`
- `max_completion_tokens ≈ 512`
- `max_total_tokens ≈ 5k`
- `max_tool_steps = 3`

---

# 8. Interaction With LLM Runtime

LLM Runtime может быть:

- локальный vLLM (через OpenAI API совместимый endpoint),
- внешняя OpenAI/Mistral/Qwen API,
- локальный сервер модели.

LLM Service должен поддерживать:

- `/v1/chat/completions`,
- JSON-mode или structured tool-calls,
- streaming-mode (опционально в будущем).

### Пример вызова:

```json
{
  "model": "local-llama-3-8b",
  "messages": [...],
  "max_tokens": 512,
  "temperature": 0.2,
  "top_p": 0.95,
  "response_format": {
    "type": "json"  // при MCP
  }
}
```

---

# 9. Error Handling

## 9.1 Ошибки модели

- timeout (превышено время генерации),
- model overloaded,
- токенизация не удалась.

Ответ:

```json
{
  "error": {
    "code": "LLM_RUNTIME_ERROR",
    "message": "Model timeout"
  }
}
```

## 9.2 Ошибки MCP

Если инструмент вернул ошибку:

- добавить сообщение вида:

```
assistant:
  {"tool_error": "..."}
```

- продолжить генерацию (модель сама выберет fallback),
- если превышено 2 ошибки подряд → прерывание.

## 9.3 Ошибки из-за лимитов

- слишком много tool-calls,
- слишком большой текст от инструмента,
- превышен token budget.

Ответ:

```json
{
  "error": {
    "code": "LLM_LIMIT_EXCEEDED",
    "message": "Tool-call limit reached"
  }
}
```

---

# 10. Non-functional Requirements

## 10.1 Performance

Цель (p95):

- latency одного вызова модели: ≤ 400–800 ms (в зависимости от модели),
- весь MCP sequence ≤ 2–3 секунд,
- overhead LLM Service ≤ 30 ms.

## 10.2 Scalability

- Stateless, горизонтальное масштабирование,
- Поддержка batch/token caching (опционально для vLLM).

## 10.3 Reliability

- retries = 1 при transient errors,
- circuit breaker к LLM runtime,
- health-check endpoint.

## 10.4 Observability

Метрики:

- `llm_requests_total`,
- `llm_latency_ms`,
- `llm_tool_call_count`,
- `llm_token_usage`,
- `llm_mcp_errors_total`.

Логи:

- model_name,
- количество tool steps,
- latency per step,
- trace_id.

---

# 11. Config

## ENV

- `LLM_RUNTIME_URL`
- `DEFAULT_MODEL_NAME`
- `MAX_TOOL_STEPS`
- `MAX_PROMPT_TOKENS`
- `MAX_COMPLETION_TOKENS`
- `ENABLE_JSON_MODE`
- `MCP_PROXY_URL`
- `LOG_LEVEL`

---

# 12. Testing

## Unit tests:

- prompt builder,
- MCP call parsing,
- token budget logic.

## Integration tests:

- LLM runtime mock,
- MCP Proxy mock,
- multi-step chain validations.

## E2E tests:

- full RAG → LLM → MCP → completion pipeline.

---

# 13. Открытые вопросы

1. Нужен ли streaming-режим в MVP?
2. Следует ли позволять модели самостоятельно делать sub-retrieval (доступ к Retrieval Service)?
3. Поддерживать ли разные типы моделей (encoder-decoder, chat, function-calling)?
4. Хранить ли промежуточные tool-call traces для последующей аналитики?

---

# END OF DOCUMENT
