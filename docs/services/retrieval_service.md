# Retrieval Service

## Назначение
Retrieval Service ищет релевантные чанки по индексам и отдаёт их AI Orchestrator. Сейчас реализована in-memory коллекция, но интерфейс повторяет production API.

## Архитектура
- FastAPI (`services/retrieval_service`).
- `core/index.InMemoryIndex` содержит список `RetrievalHit`.
- Конфигурация через `RETR_*`.

## Конфигурация
| Переменная | Описание |
| --- | --- |
| `RETR_MAX_RESULTS` | Максимум документов в ответе (по умолчанию 5). |
| `RETR_MOCK_MODE` | Использовать встроенный индекс. |

## API
### `POST /internal/retrieval/search`
**Request**
```json
{
  "query": "LDAP",
  "tenant_id": "tenant_1",
  "max_results": 3
}
```
**Response**
```json
{
  "hits": [
    {
      "doc_id": "doc_1",
      "section_id": "sec_intro",
      "chunk_id": "chunk_1",
      "text": "LDAP intro",
      "score": 0.98,
      "page_start": 1,
      "page_end": 2
    }
  ]
}
```

## Расширение
- Для подключения реального векторного хранилища реализуйте адаптер в `core/index.py` с тем же интерфейсом `search(query: RetrievalQuery) -> List[RetrievalHit]`.
- Добавляя новые поля (например, `confidence`), обновите `schemas.RetrievalHit`, mock данные и клиента в AI Orchestrator.

## Mock требования
- Даже в mock режиме результирующий JSON должен содержать ключ `hits`. Оркестратор допускает также список верхнего уровня, но стандарт — объект.
- Значения `doc_id`/`section_id` должны быть стабильно воспроизводимыми для сквозных тестов (`tests/test_pipeline_integration.py`).

