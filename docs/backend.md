# Backend Architecture Documentation
## Orion Soft Internal AI Assistant

---

## 1. Goals & Non‑Goals

### 1.1 Goals
- Создать надёжный и расширяемый backend для AI‑ассистента с RAG.
- Поддержать многоступенчатый retrieval (doc → section → chunk).
- Обеспечить безопасную обработку запросов (Input/Output Safety).
- Поддержать ingestion документов: парсинг, chunking, summary, embeddings.
- Инкапсулировать работу с LLM через единый сервис (LLM Gateway).
- Обеспечить простой для разработки микросервисный дизайн.

### 1.2 Non‑Goals
- Не создавать чрезмерно сложный сервис‑мэш.
- Не описывать низкоуровневые API‑эндпоинты.
- Не привязываться к конкретному вендору LLM/VectorDB.

---

## 2. High-Level Architecture

### 2.1 Services Overview
- **API Gateway**
- **AI Orchestrator**
- **Safety Service** (Input Guard + Output Guard)
- **Retrieval Service**
- **LLM Service** (RAG + MCP tool-calls)
- **Ingestion Service**
- *(optional)* **Tools/MCP Proxy**

### 2.2 Infrastructure Components
- **Vector DB** — хранение doc/section/chunk embeddings.
- **Document Store** — PDF/Docx файлы.
- **Metadata DB** — документы, секции, статусы ingestion, пользователи.
- **Message Broker** — асинхронные задачи.
- **Policy Store** — правила безопасности и RBAC.
- **Logging & Metrics** — централизованные логи и метрики.

---

## 3. Service Responsibilities

---

### 3.1 API Gateway
**Responsibilities:**
- Принимает запросы клиентов (Web/Chat/Integrations).
- AuthN/AuthZ: JWT / OAuth2 / SSO.
- Rate limiting.
- Вызов Safety Input Guard.
- Роутинг запросов в AI Orchestrator.
- Роутинг upload‑запросов в очередь ingestion.
- Генерация trace_id и логирование.

**Not responsible for:**
LLM, RAG, VectorDB.

---

### 3.2 Safety Service
**Subcomponents:**
- **Input Guard**
- **Output Guard**

**Input Guard responsibilities:**
- Content safety (вред, терроризм, взлом и др.).
- PII/DLP фильтрация (пароли, секреты, токены).
- Tenant isolation и RBAC.
- Sanitize/transform/deny запроса.

**Output Guard responsibilities:**
- Проверка ответа от LLM.
- Фильтрация опасного или расходящегося с политикой контента.
- Проверка leakage: секреты, внутренние конфиги, tenant‑данные.
- Санитизация или блокировка ответа.

---

### 3.3 AI Orchestrator
**Role:** главный управляющий компонент AI‑пайплайна.

**Responsibilities:**
- Получение «чистого» запроса от API Gateway.
- Определение типа запроса.
- Управление retrieval‑процессом:
  - doc/section/chunk search (через Retrieval Service),
  - reranking,
  - построение контекста (token budget).
- Формирование промпта для LLM Service.
- Обработка MCP tool‑calls от LLM.
- Передача candidate response через Output Guard.
- Обработка ошибок, timeouts, fallback.
- Полный trace цепочки.

---

### 3.4 Retrieval Service
**Responsibilities:**
- **Document‑level retrieval**.
- **Section‑level retrieval** (основная точка входа).
- **Chunk‑level retrieval**.
- Hybrid search: dense + BM25.
- Reranking (rule-based or ML).
- Context builder:
  - токен‑лимит,
  - разнообразие документов,
  - приоритет релевантных секций.
- Возврат готового набора чанков + источников.

**Data Access:**
- Vector DB для индексов.
- Metadata DB для документов/секций.

---

### 3.5 LLM Service
**Responsibilities:**
- Обёртка над LLM (локальная/внешняя).
- Chat + RAG inference.
- Prompt construction (system + context + user).
- Tool‑call handler (MCP):
  - чтение разделов документа,
  - поиск по документам,
  - безопасные внутренние API.
- Управление параметрами модели (температура, max tokens).

---

### 3.6 Ingestion Service
**Responsibilities:**
- Асинхронный ingestion после загрузки документа.
- Парсинг PDF/Docx.
- Разбиение на секции и чанки.
- Генерация summary.
- Получение embeddings (doc/section/chunk).
- Запись индексов в Vector DB.
- Обновление статуса документа.
- Логирование ошибок ingestion.

---

## 4. Data Layer

---

### 4.1 Vector DB Structure
- `doc_index`:
  - doc_id
  - doc_embedding
  - metadata
- `section_index`:
  - section_id
  - summary
  - summary_embedding
  - doc_id
- `chunk_index`:
  - chunk_id
  - chunk_text
  - chunk_embedding
  - doc_id, section_id
  - token_count
  - page ranges / offsets for MCP

---

### 4.2 Metadata DB Schema
Entities:

**documents**
- doc_id
- name
- source
- tags
- file_path
- product / version
- status (`uploaded`, `processing`, `indexed`, `failed`)
- timestamps

**sections**
- section_id
- doc_id
- title
- pages
- summary

**chunks**
- chunk_id
- doc_id
- section_id
- text
- tokens
- page ranges

**ingestion_jobs**
- job_id
- doc_id
- status
- error_log

---

## 5. Message Broker Usage

Queues/topics:
- `documents_to_ingest` — ingestion pipeline.
- `document_ingested`, `ingestion_failed` — события.
- `audit_events` — логи безопасности/LLM.

Minimal guarantees:
- At‑least‑once delivery.
- Dead-letter queue for ingestion failures.

---

## 6. Cross‑Cutting Concerns

### 6.1 Observability
- Central logging system (trace_id on all logs).
- Metrics:
  - latency по сервисам,
  - ошибки по сервисам,
  - LLM token usage,
  - ingestion throughput,
  - safety block/allow ratio.
- Distributed tracing (OpenTelemetry).

---

### 6.2 Security
- TLS everywhere (external + internal).
- mTLS или сетевые ACL для внутренних сервисов.
- Safety‑контур:
  - Input Guard → защищает inference pipeline,
  - Output Guard → защищает пользователя/данные.
- Secrets management: никакие токены в коде, только vault.

---

### 6.3 Scalability
- Stateless сервисы масштабируются горизонтально:
  - API Gateway
  - AI Orchestrator
  - Retrieval Service
  - LLM Service
  - Safety Service
- Ingestion Service масштабируется количеством воркеров.
- Vector DB и Metadata DB — кластер.

---

## 7. Main System Flows

---

### 7.1 User Query Flow

1. UI → API Gateway
2. API Gateway → Safety Input Guard
3. API Gateway → AI Orchestrator
4. Orchestrator → Retrieval Service → Vector DB
5. Orchestrator → LLM Service (RAG)
6. LLM Service ↔ MCP (опциональные tool‑calls)
7. LLM Service → Orchestrator
8. Orchestrator → Safety Output Guard
9. Orchestrator → API Gateway → UI

---

### 7.2 Document Ingestion Flow

1. UI → API Gateway → enqueue `documents_to_ingest`
2. Ingestion Service consumes task
3. Parses → chunks → summaries → embeddings
4. Writes to Vector DB / Metadata DB
5. Updates status (`indexed`)

---

# Summary

Эта backend архитектура:

- Простая в реализации (HTTP + очереди).
- Устойчиво масштабируется по нагрузке.
- Изолирует сложность AI‑пайплайна в Orchestrator и LLM Service.
- Обеспечивает безопасную обработку запросов (OWASP LLM Top‑10).
- Легко расширяется за счёт отдельного ingestion и retrieval слоёв.
