# Техническое задание — Retrieval Service

## 1. Назначение
Выполнять поиск релевантных doc/section/chunk сущностей для AI Orchestrator и ML Observer. Поддерживает Chroma backend и in-memory mock режим, фильтры по tenant и метаданным, опциональный rerank.

## 2. API (prefix `/internal/retrieval`)
- `POST /search` — поля: `query`, `tenant_id`, опц. `max_results`, `filters{product,version,tags,doc_ids,section_ids}`, `doc_ids`, `section_ids`, `enable_filters`, `rerank_enabled`, `trace_id`. Ответ: `hits` (список `RetrievalHit` без поля `text`, только id/summary/метаданные/score), опц. `steps{docs,sections,chunks}`.
- `GET /config` — возвращает текущие настройки (max_results, topK, rerank, фильтры).
- `POST /config` — частично обновляет настройки.
- `POST /chunks/window` — `tenant_id`, `doc_id`, `anchor_chunk_id`, опц. `window_before`, `window_after` → `{"chunks": [{chunk_id, page, chunk_index, text}]}`; это единственный эндпоинт, возвращающий raw text.
- `/health` — `{"status":"ok"}`; в prod режиме добавляет `backend: chroma` и ошибку при недоступности.

## 3. Поисковая логика (ChromaIndex)
1. Строит where по tenant + фильтрам; может отключать фильтры, если `enable_filters=false`.
2. Doc-level: query embeddings → topK из `ingestion_docs`; при нехватке дополняет метаданными (`_pad_docs_with_metadata`).
3. Section-level: поиск по `ingestion_sections`, опционально rerank через OpenAI chat completions (модель `RETR_RERANK_MODEL`, top_n `RETR_RERANK_TOP_N`).
4. Chunk-level: поиск в `ingestion_chunks` c фильтрами по doc/section, применяет `topk_per_doc` и `max_results`; fallback `_fallback_metadata_search` по тексту при пустом результате. Поле `text` всегда вырезано из ответа; summary/title используются как краткое описание.
5. Возвращает section hits, если они есть, иначе chunk hits. `steps` содержит промежуточные результаты; `steps.chunks` может быть пустым и не используется для начального промпта.

## 4. Конфигурация (`RETR_*`)
`mock_mode`, `vector_backend` (chroma), `chroma_path/host/collection`, `max_results` (кап 50), `topk_per_doc`, `min_score`, `doc_top_k`, `section_top_k`, `chunk_top_k`, `min_docs`, `enable_filters`, `embedding_api_base/key/model`, `embedding_max_attempts`, `embedding_retry_delay_seconds`, `rerank_enabled`, `rerank_model`, `rerank_api_base/key`, `rerank_top_n`.

## 5. Дополнительно
- EmbeddingClient использует OpenAI-style `/v1/embeddings`; при ошибках — псевдо-эмбеддинги (SHA256) и лог предупреждения.
- `SectionReranker` использует OpenAI chat completions и ждёт JSON [{section_id, score}] в ответе; при ошибке возвращает исходный порядок.
- Chunk window (`/chunks/window`) сортирует все найденные чанки документа по `page/chunk_index`, ищет anchor и возвращает окно `[before..after]`.
