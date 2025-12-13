# Retrieval Service — progress

## Что уже реализовано
- Эндпоинты `/internal/retrieval/search` и `/health` на FastAPI (`routers/retrieval.py`, `main.py`).
- In-memory индекс с предзагруженными хитами для mock режима; ChromaIndex адаптер, который строит `where` по `tenant_id/doc_ids/section_ids/product/version/tags` и ищет в коллекции через chromadb клиент.
- Конфиг через `RETR_*` (`config.py`): mock_mode, max_results/topk_per_doc/min_score, backend и Chroma настройки, embedding API параметры.
- Ограничение `max_results` (min with config и 50) на уровне маршрута.
- Возврат ошибок backend как 502 `backend_unavailable`.
- Тест поиска в mock-интерфейсе (`services/retrieval_service/tests/test_search.py`).

## Как это реализовано
- Приложение инициализирует индекс при старте: InMemoryIndex при `mock_mode=true`, либо ChromaIndex с EmbeddingClient (генерирует вектор для запроса) и persistent/HTTP chroma клиентом.
- ChromaIndex: строит `where` фильтр, извлекает `n_results` (увеличенный, если есть topk_per_doc), маппит метаданные в `RetrievalHit` (score = 1 - distance), применяет per-doc limit/topk и `max_results`, fallback метаданных (substring match) если результатов нет.
- Health: проверка Chroma доступности (count) при немок режиме.
- Схемы поддерживают фильтры `product/version/tags/doc_ids/section_ids`, но применяются только часть (doc_ids, section_ids, product/version/tags) в ChromaIndex.

## Что осталось сделать / отклонения от ТЗ
- Нет обязательной проверки `tenant_id` в роуте/индексе (используется только в фильтре Chroma, но InMemoryIndex не фильтрует по tenant); X-Request-ID и auth отсутствуют.
- Фильтры по метаданным не применяются в in-memory режиме; нет doc-level/section-level многоступенчатого поиска (только прямой запрос по embeddings/fallback substring).
- Отсутствуют параметры/ограничения `topk_per_doc` в mock (игнорируются), `min_score` не применяется в mock.
- Наблюдаемость: нет метрик/логирования latency/кол-ва результатов, health не проверяет embedding backend.
- Отказоустойчивость: нет таймаутов/ретраев для Chroma/embedding; ошибки превращаются в 502 без кода `backend_unavailable` деталей (хотя detail содержит code).
- Документация/функционал для doc_service фильтров/валидации не реализованы; min_score/topk_per_doc не описаны в API документации текущей версии (docs/services/retrieval_service.md).
