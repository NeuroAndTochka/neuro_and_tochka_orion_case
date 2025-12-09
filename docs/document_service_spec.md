# Technical Specification (TZ)
## Microservice: **Document Service (Metadata & Access API)**
### Project: Orion Soft Internal AI Assistant — *Visior*

---

# 1. Назначение сервиса

Document Service предоставляет API для управления метаданными документов, статусов ingestion и доступа к подготовленным представлениям (sections/pages) без выдачи оригинальных файлов. Он используется API Gateway, Ingestion Service, MCP Tools Proxy и Retrieval для получения структурированной информации о документах и проверок tenant isolation.

---

# 2. Область ответственности

## 2.1 Входит в ответственность

1. Хранение метаданных документов (название, версия, теги, продукт, tenant, статусы).
2. Хранение структуры документа (sections/pages) и ссылок на chunk IDs для Retrieval.
3. API для списка документов, фильтров, поиска по тегам/названиям.
4. API для получения детальной информации по doc_id, включая секции и доступные инструменты (нап. путь для MCP).
5. Интеграция с Ingestion Service: обновление статусов, сохранение результатов парсинга.
6. Проверка прав доступа (tenant isolation, роли пользователя).

## 2.2 Не входит в ответственность

- Хранение сырых файлов (S3/MinIO).
- Выдача бинарных данных документа.
- Выполнение Retrieval-поиска (это Retrieval Service).
- Safety-проверки текстов (это Safety Service).

---

# 3. Высокоуровневая архитектура

```
API Gateway / MCP / Retrieval → Document Service → PostgreSQL (metadata) + Object storage references
                                              ↘ Cache (Redis) для частых запросов
```

Сервис stateless, данные лежат в PostgreSQL (таблицы: `documents`, `document_sections`, `document_versions`, `document_tags`). Взаимодействие с Ingestion Service по gRPC/REST webhook.

---

# 4. Модель данных

- `documents`
  - `doc_id` (UUID)
  - `tenant_id`
  - `name`
  - `product`
  - `version`
  - `status` (uploaded, processing, indexed, failed)
  - `storage_uri`
  - `created_at`, `updated_at`
- `document_sections`
  - `section_id`
  - `doc_id`
  - `title`
  - `page_start`, `page_end`
  - `summary`
  - `chunk_ids` (jsonb)
- `document_tags`
  - `doc_id`
  - `tag`

---

# 5. API эндпоинты

Все эндпоинты находятся под `/internal/documents`, требуют service token и заголовки `X-Tenant-ID`, `X-Request-ID`.

## 5.1 `GET /internal/documents`
Список документов с пагинацией и фильтрами (`status`, `product`, `tag`, `search`).

**Response**
```json
[
  {
    "doc_id": "doc_123",
    "name": "Orion LDAP Guide",
    "status": "indexed",
    "product": "Orion X",
    "version": "1.2",
    "tags": ["ldap", "admin"],
    "updated_at": "2025-12-03T10:20:00Z"
  }
]
```

## 5.2 `GET /internal/documents/{doc_id}`
Возвращает полную структуру документа, включая секции.

```json
{
  "doc_id": "doc_123",
  "title": "Orion LDAP Guide",
  "pages": 142,
  "sections": [
    {
      "section_id": "sec_intro",
      "title": "Введение",
      "page_start": 1,
      "page_end": 3,
      "chunk_ids": ["chunk_1", "chunk_2"]
    }
  ],
  "tags": ["ldap", "on-prem"],
  "tenant_id": "tenant_1"
}
```

## 5.3 `POST /internal/documents/status`
Batch-обновление статусов ingestion.

**Request**
```json
{
  "doc_id": "doc_123",
  "status": "indexed",
  "error": null
}
```

## 5.4 `GET /internal/documents/{doc_id}/sections/{section_id}`
Возвращает конкретную секцию (метаданные + ссылку на текст в storage/MCP).

---

# 6. Интеграция с другими сервисами

| Сервис              | Вызов/Событие                           | Назначение                               |
|---------------------|----------------------------------------|------------------------------------------|
| Ingestion Service   | `POST /internal/documents/status`      | Обновление статуса/структуры             |
| Retrieval Service   | `GET /sections` + gRPC `GetChunkInfo`  | Получение chunk metadata и tenant check  |
| MCP Tools Proxy     | `GET /documents/{id}` + `/sections`    | Валидация doc_id и извлечение диапазонов |
| API Gateway         | `GET /documents`, `/upload` callbacks  | UI/управление документами                |

---

# 7. Безопасность и управление доступом

- Каждый запрос должен содержать `tenant_id`; сервис проверяет, принадлежит ли doc этому tenant.
- Роли пользователя (из JWT, прокинутые API Gateway) определяют доступ к документам (например, `doc_admin`, `viewer`).
- Логи не содержат текстов документов; только идентификаторы и метаданные.
- Поддержка soft-delete для документов (флаг `deleted_at`).

---

# 8. Конфигурация (ENV)

| Переменная                     | Описание                                  |
|--------------------------------|-------------------------------------------|
| `DOC_DB_DSN`                   | DSN PostgreSQL                            |
| `DOC_CACHE_URL`                | Redis для кэша                            |
| `DOC_STORAGE_BASE`             | S3/MinIO bucket URI                       |
| `DOC_MAX_PAGE_RANGE`           | Ограничение выдачи страниц (например, 5)  |
| `DOC_DEFAULT_PAGE_SIZE`        | Размер пагинации                          |
| `LOG_LEVEL`                    | Уровень логирования                       |
| `ENABLE_AUDIT_LOG`             | Включение аудита                          |

---

# 9. Тестирование

## Unit
- Проверка фильтров и построения SQL.
- Проверка правил tenant isolation.

## Integration
- Тесты с PostgreSQL/Redis (docker-compose).
- Поток Ingestion → Document Service → Retrieval.

## Performance
- Нагрузочный тест списка документов (пагинация с фильтрами).
- Stress test на массовое обновление статусов.

---

# 10. Observability

Метрики: `document_status_total`, `document_list_latency_ms`, `document_section_hits_total`.

Логи: trace_id, doc_id, action (read/list/update), status, caller_service.

Аудит: кто запросил документ, в какой канал отправлен ответ (для compliance).

---

# 11. Открытые вопросы

1. Нужно ли версионировать метаданные (history of changes)?
2. Нужен ли граф зависимостей документов (для наборов знаний)?
3. Следует ли выдавать превью страниц (rendered HTML) как отдельный сервис?

---

# 12. Итог

Document Service покрывает менеджмент метаданных и обеспечивает безопасный доступ к структурированной информации о документах, что критично для корректной работы Retrieval, MCP и UI.
