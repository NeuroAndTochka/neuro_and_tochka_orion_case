# Документация по backend-архитектуре
## Orion Soft Internal AI Assistant — Visior

---

## 1. Цели и ограничения
### 1.1 Цели
- Построить надёжный и расширяемый backend для RAG-ассистента.
- Поддержать многоступенчатый retrieval (doc → section → chunk) и гибкую оркестрацию.
- Гарантировать безопасность (Input/Output Safety, tenant isolation).
- Автоматизировать ingestion: парсинг, chunking, summary, embeddings.
- Инкапсулировать работу с LLM/Tooling в отдельных сервисах.
- Сохранить модульность и простоту для команды разработки.

### 1.2 Не цели
- Создавать сложный сервис-мэш или tightly coupled монолит.
- Привязываться к конкретному вендору LLM/VectorDB.
- Детально описывать UI и клиентские приложения.

---

## 2. Высокоуровневая архитектура
### 2.1 Сервисы
- **API Gateway** — edge-слой, авторизация, safety input, документы.
- **AI Orchestrator** — orchestration RAG, вызов Retrieval/LLM/Safety.
- **Safety Service** — input guard + output guard.
- **Retrieval Service** — поиск по векторам/метаданным.
- **LLM Service** — генерация, tool-loop, MCP.
- **Ingestion Service** — обработка и индексация документов.
- **MCP Tools Proxy** — исполнение инструментов (по требованию).
- **Document Service** — метаданные, статусы, секции.

### 2.2 Инфраструктура
- **Vector DB** (doc/section/chunk embeddings).
- **Object Storage** (PDF/Docx).
- **Metadata DB** (PostgreSQL/похожая СУБД).
- **Message Broker** (очереди ingestion, уведомления).
- **Policy Store** (OPA/Rego, конфиги security).
- **Logging & Metrics** (ELK/Prometheus, централизованные trace).

---

## 3. Ответственность сервисов
### 3.1 API Gateway
- Принимает внешние запросы (UI, чат, интеграции).
- Выполняет AuthN/AuthZ и rate limit.
- Вызывает Safety input guard.
- Отправляет payload в Orchestrator и downstream сервисы.
- Управляет загрузкой документов → Ingestion Service.
- Формирует trace_id и обеспечивает аудит.

### 3.2 AI Orchestrator
- Принимает нормализованный запрос.
- Инициирует поиск (Retrieval Service), собирает контекст.
- Подготавливает payload для LLM Service.
- Вызывает Safety output guard и формирует ответ.
- Сохраняет телеметрию (latency, tool_steps, источник).

### 3.3 Safety Service
- Input guard (блокировка вредоносных или PII-запросов).
- Output guard (sanitize/block ответов LLM).
- Логи + статистика по политикам.

### 3.4 Retrieval Service
- Запрос к Vector DB + keyword search.
- Объединение doc/section/chunk результатов.
- Reranking, построение context_chunks.

### 3.5 LLM Service
- Принимает GenerateRequest от Orchestrator.
- Вызывает runtime (OpenAI-compatible или on-prem модель).
- Управляет MCP tool-call циклом, возвращает telemetry, usage, sources.

### 3.6 MCP Tools Proxy
- Реализует инструменты (read_doc_section, local_search и т.п.).
- Ограничивает вызовы (rate limit, policy).

### 3.7 Ingestion Service
- Получает задания на обработку документов.
- Парсит, chunk'ит, строит summary и embeddings.
- Обновляет статусы и публикует события (`document_ingested`, `ingestion_failed`).

### 3.8 Document Service
- Хранит метаданные, секции, историю статусов.
- Предоставляет API для Gateway, MCP, Retrieval.

---

## 4. Потоки данных
### 4.1 Пользовательский запрос
1. UI → API Gateway (Auth + rate limit + input safety).
2. Gateway → Orchestrator (`trace_id`, user context, safety результат).
3. Orchestrator → Retrieval Service (поиск контекста).
4. Orchestrator → LLM Service (RAG + MCP loop).
5. LLM Service ↔ MCP Tools Proxy (при необходимости).
6. Orchestrator → Safety output.
7. Orchestrator → Gateway → UI (ответ + источники + метаданные).

### 4.2 Ingestion
1. Upload (Gateway) → Ingestion Service (через queue/REST).
2. Ingestion скачивает документ, парсит, формирует секции/чанки.
3. Сохраняет embeddings в Vector DB, метаданные в Document Service.
4. Публикует событие `document_ingested` или `ingestion_failed`.
5. Gateway/Document Service обновляют статусы для UI.

---

## 5. Безопасность
- Двойной safety-контур (input/output).
- Tenant isolation на уровне токенов, заголовков и хранилищ.
- Логирование trace_id, user_id, tenant_id, status.
- Rate limit на пользователе/tenant/ip.
- MCP-инструменты работают в sandbox и проверяются Safety.

---

## 6. Наблюдаемость
- Метрики latency по каждому сервису (p50/p95/p99).
- Количество safety-блокировок/санитизаций.
- Ингестия: throughput, % отказов, среднее время обработки.
- MCP usage: количество tool-call'ов, top tools.
- Health endpoint'ы (/api/v1/health, /internal/health/*).

---

## 7. Деплой и тестирование
- Локально: `docker compose up --build`.
- Тестирование: `pytest` в корне запускает unit + e2e (`tests/test_pipeline_integration.py`).
- Линтинг: `pre-commit run --all-files` (flake8 + базовые хуки).
- CI: GitHub Actions (`.github/workflows/ci.yml`).
- Production: Kubernetes (Deployment + HPA) или аналогичная платформа.

---

## 8. Следующие шаги
- Расширить observability (добавить tracing exporter).
- Настроить полноценный Vector DB и storage для ingestion.
- Подключить внешние интеграции (чат-боты, порталы).
- Расширить набор MCP инструментов и safety-политик.
