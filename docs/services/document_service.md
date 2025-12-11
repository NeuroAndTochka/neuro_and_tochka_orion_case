# Document Service

## Назначение
Document Service хранит метаданные документов, секций и статусы обработки. Используется API Gateway (для отображения пользователю) и ingestion pipeline (для обновления статусов).

## Архитектура
- FastAPI приложение (`services/document_service`).
- In-memory репозиторий (`core/repository.InMemoryRepository`). В бою заменяется на БД или кэш.
- Конфигурация через `DOC_*`.

## Конфигурация
| Переменная | Описание |
| --- | --- |
| `DOC_DB_DSN` | Подключение к БД (заглушка). |
| `DOC_CACHE_URL` | Redis/кэш для ускорения. |
| `DOC_MOCK_MODE` | Использовать встроенные данные. |

## API
Все запросы требуют заголовок `X-Tenant-ID`.

### `GET /internal/documents`
Параметры: `status`, `product`, `tag`, `search`. Возвращает список `DocumentItem`.

```bash
curl -H "X-Tenant-ID: tenant_1" "http://doc.local/internal/documents?status=ready"
```

### `GET /internal/documents/{doc_id}`
Возвращает `DocumentDetail` (включая секции, страницы).

### `GET /internal/documents/{doc_id}/sections/{section_id}`
Возвращает `DocumentSection`.

### `POST /internal/documents/status`
Body:
```json
{
  "doc_id": "doc_1",
  "status": "ready",
  "error": null
}
```
Возвращает обновлённый `DocumentItem`.

## Расширение
- Для реальной БД создайте класс репозитория и зарегистрируйте через `app.state.repository` в `main.py`.
- Добавляя новые поля в документы, обновляйте `schemas.py`, mock-данные в репозитории и внешние клиенты API Gateway.

## Mock требования
- InMemoryRepository должен отражать полную структуру документа (ID, tenant, секции, страницы). Любые новые поля нужно добавлять во все заглушки, иначе фронт получит `KeyError`.
- В тестах используйте фикстуру, которая инициализирует репозиторий одинаковыми данными (`services/document_service/tests/test_documents.py`).

