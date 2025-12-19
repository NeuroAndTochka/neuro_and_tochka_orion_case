# Retrieval Service

## Назначение
Ступенчатый поиск по doc/section/chunk метаданным/эмбеддингам (Chroma) или по in-memory моковым данным. Используется AI Orchestrator, ML Observer и MCP chunk window.

## Эндпоинты (`/internal/retrieval`)
- `POST /search` — `query`, `tenant_id`, опц. `max_results`, `filters{product,version,tags,doc_ids,section_ids}`, `doc_ids`, `section_ids`, `enable_filters`, `rerank_enabled`, `trace_id`. Ответ: `hits` (doc/section/chunk без поля `text`, только id/summary/score/метаданные), опц. `steps{docs,sections,chunks}`.
- `GET/POST /config` — текущие/новые значения `max_results`, `topk_per_doc`, `min_score`, `doc_top_k`, `section_top_k`, `chunk_top_k`, `rerank_enabled/model/top_n`, `enable_filters`, `min_docs`.
- `POST /chunks/window` — `tenant_id`, `doc_id`, `anchor_chunk_id`, опц. `window_before/after`. Возвращает отсортированное окно чанков вокруг anchor (единственный endpoint с raw текстом).
- `/health` — `{"status":"ok"}` и, в prod-режиме, проверка доступности Chroma.

## Поведение поиска (ChromaIndex)
1. Встраивает запрос через `EmbeddingClient` (OpenAI-style или псевдо-эмбеддинги в mock режиме).
2. Doc-level topK (коллекция `ingestion_docs`), при нехватке паддит по метаданным.
3. Section-level topK (коллекция `ingestion_sections`), опционально rerank через OpenAI Chat completions.
4. Chunk-level отбор (коллекция `ingestion_chunks`), фильтры per-doc (`topk_per_doc`), отсев по `min_score`; `text` из метаданных не возвращается, используется только summary/title.
5. Возвращает section hits, если они есть, иначе chunk hits (chunk-результаты могут быть пустыми). Метаданные `page_start/page_end/title/summary/chunk_ids` заполняются из коллекций; сырой текст доступен только через `/chunks/window`.

## Конфигурация (`RETR_*`)
`mock_mode`, `vector_backend`, `chroma_path/host/collection`, `max_results`, `topk_per_doc`, `min_score`, `doc_top_k`, `section_top_k`, `chunk_top_k`, `enable_filters`, `min_docs`, `embedding_api_base/key/model`, `embedding_max_attempts`, `embedding_retry_delay_seconds`, `rerank_enabled`, `rerank_model`, `rerank_api_base/key`, `rerank_top_n`.
