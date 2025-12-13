# Процесс Ingestion (Visior)

Документ фиксирует текущее состояние пайплайна ingestion в `ingestion_service` (ветка `main`) и точки расширения.

## Цели
- Принимать файлы от API Gateway (через его прокси).
- Сохранять исходники в S3/MinIO или локальное хранилище.
- Регистрировать документ и секции в Document Service.
- Делать chunking + 3 уровня эмбеддингов (doc/section/chunk) и LLM-саммари секций.
- Поддерживать локальную разработку в mock-режиме (псевдо-эмбеддинги, локальный storage, SQLite в Document Service).

## Архитектура (текущая)
```
API Gateway → ingestion_service (/internal/ingestion/enqueue)
                 ├─ StorageClient (S3/MinIO, local://, либо файловая система)
                 ├─ JobStore (in-memory или Redis)
                 ├─ Очередь (Redis list или in-memory) + встроенные воркеры
                 ├─ EmbeddingClient (OpenAI-совместимый endpoint либо mock)
                 ├─ Summarizer (OpenAI-совместимый endpoint либо fallback)
                 ├─ VectorStore (Chroma, отключён в mock_mode)
                 └─ Background task: pipeline.process_file
                        ├─ download_bytes → parse → pages/sections/chunks
                        ├─ embeddings: doc / section / chunk
                        ├─ LLM summary секций
                        ├─ upsert секций + статус в Document Service
                        └─ upsert в vector store
```

## Конфигурация (важные `INGEST_*`)
- Режимы: `INGEST_MOCK_MODE` (`true` по умолчанию) — включает локальный storage, псевдо-эмбеддинги, отключает Chroma.
- Хранилище:
  - `INGEST_S3_ENDPOINT`, `INGEST_S3_BUCKET`, `INGEST_S3_ACCESS_KEY`, `INGEST_S3_SECRET_KEY`, `INGEST_S3_REGION`, `INGEST_S3_SECURE`
  - `INGEST_LOCAL_STORAGE_PATH` — папка для `local://` в mock-режиме.
  - `INGEST_STORAGE_PATH` — fallback путь (по умолчанию `/var/lib/visior_ingestion_storage`).
- Document Service: `INGEST_DOC_SERVICE_BASE_URL` — если задан, пайплайн создаёт/обновляет документ, секции и статусы.
- Очередь/JobStore: `INGEST_REDIS_URL` — при наличии Redis использует его как бекенд; иначе in-memory (волатильно). `INGEST_WORKER_COUNT` — число воркеров (по умолчанию 1), `INGEST_QUEUE_NAME` — имя очереди, `INGEST_MAX_ATTEMPTS` и `INGEST_RETRY_DELAY_SECONDS` — ретраи.
- Эмбеддинги (OpenAI-style): `INGEST_EMBEDDING_API_BASE`, `INGEST_EMBEDDING_API_KEY`, `INGEST_EMBEDDING_MODEL` (по умолчанию `baai/bge-m3` в compose).
- Summarizer (OpenAI-style): `INGEST_SUMMARY_API_BASE`, `INGEST_SUMMARY_API_KEY`, `INGEST_SUMMARY_MODEL`, `INGEST_SUMMARY_REFERER`, `INGEST_SUMMARY_TITLE`.
- Retrieval: `INGEST_RETRIEVAL_BASE_URL` (зарезервировано для будущих шагов).
- Чанк/лимиты: `INGEST_MAX_PAGES`, `INGEST_MAX_FILE_MB`, `INGEST_CHUNK_SIZE`, `INGEST_CHUNK_OVERLAP`.
- Vector store: `INGEST_CHROMA_PATH` — путь для Chroma PersistentClient (работает только если `mock_mode=false` и chromadb установлен).

## Публичные API
Все запросы требуют заголовок `X-Tenant-ID`.

- `POST /internal/ingestion/enqueue` — multipart `file`, опц. `product|version|tags`. Возвращает `job_id`, `doc_id`, `status`, `storage_uri`. Создаёт запись в JobStore, опционально регистрирует документ в Document Service и запускает фоновой пайплайн.
- `POST /internal/ingestion/status` — обновляет статус job, пушит статус в Document Service (если настроен). Тело: `job_id`, `status`, `error?`.
- `GET /internal/ingestion/jobs/{job_id}` — статус и логи job (до 50 последних записей).
- `GET/POST /internal/ingestion/summarizer/config` — чтение/обновление конфигурации summarizer (model, prompt, max_tokens, use_roles).
- `GET /internal/ingestion/documents/{doc_id}/tree` — дерево секций из Document Service + чанки из vector store (если включён).

## Pipeline `process_file` (фон)
1. Скачивание исходника (`StorageClient`): S3 → bytes, либо `local://`/file-path.
2. Парсинг: `DocumentParser` (PDF/DOCX) возвращает страницы и мета; fallback — чистка текста.
3. Чанкование: `_build_sections_from_pages` строит секции/чанки по `chunk_size`, генерирует `section_id`/`chunk_id`.
4. Эмбеддинги: document + sections + chunks через `EmbeddingClient`; в mock режиме — псевдо-векторы по SHA256. Логи вызовов сохраняются в JobStore.
5. LLM summary секций: `Summarizer` (OpenAI API или fallback на обрезанный текст). Пэйлоады/ответы логируются.
6. Формирование секций: добавление `embedding` в payload для Document Service.
7. Document Service: `/internal/documents/{doc_id}/sections` + `/internal/documents/status` (`indexed`, `pages`), если указан `INGEST_DOC_SERVICE_BASE_URL`.
8. Vector store: upsert doc/sections/chunks в Chroma (если включён).
9. Финал: обновление job → `indexed` или `failed`, публикация события в JobStore (Redis stream при наличии).

## Docker Compose (локально/стейдж)
- MinIO + бакет `visior-documents` на `http://localhost:9000`.
- Ingestion/Document запускаются с `MOCK_MODE=false` и MinIO/Chroma/Redis (для демонстрации); требуется задать `INGEST_SUMMARY_API_KEY`/`INGEST_EMBEDDING_API_KEY`.
- Redis доступен, но очередь всё ещё фоновые задачи FastAPI — персистентности нет.

## Ограничения и планы
- Нет реальной очереди/воркеров (только in-memory/Redis store + background task).
- Нет ретраев S3/LLM/Document Service; ошибки падают в `failed`.
- Парсинг/чанкование упрощены, нет overlap/сегментации по заголовкам.
- Разделение section/chunk условное; rerank не реализован.
- Требуются интеграционные тесты с MinIO/Chroma и устойчивое управление ключами OpenAI/OpenRouter.

## Быстрый старт
```bash
docker compose up --build
# или без Docker (mock):
cd services/ingestion_service
export INGEST_MOCK_MODE=true
pip install -e '.[dev]'
uvicorn ingestion_service.main:app --reload --port 8050
```
