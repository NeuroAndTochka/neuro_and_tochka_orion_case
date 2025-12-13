# MCP Tools Proxy — progress

## Что уже реализовано
- Эндпоинты `/internal/mcp/execute` и `/health` на FastAPI (`main.py`, `routers/mcp.py`).
- Реестр инструментов (`core/executor.ToolRegistry`) с инициализацией mock DocumentRepository и регистрацией инструментов чтения документа/секций/страниц, локального поиска и списка доступных (`tools/*.py`).
- Rate limiting на количество вызовов и оценку токенов (`core/rate_limit.ToolRateLimiter`) с возвратом кода `RATE_LIMIT_EXCEEDED`.
- Проверка tenant-доступа по doc_id во всех инструментах, обрезка текста по `max_text_bytes`, лимит страниц на вызов.
- Схемы запросов/ответов MCP (`schemas.py`) и базовые тесты на успешное выполнение, доступ, rate-limit и list-tools (`services/mcp_tools_proxy/tests`).
- Конфигурация через `MCP_PROXY_*` (`config.py`): лимиты по страницам/байтам/количеству вызовов/токенам, blocklist, mock_mode.

## Как это реализовано
- `ToolRegistry.execute` ищет инструмент, собирает `ToolExecutionContext` с `trace_id` (по умолчанию `trace-unknown`), оценивает `estimated_tokens`=100, проверяет `ToolRateLimiter`, затем вызывает tool; HTTPException перехватывается и оборачивается в `MCPExecuteResponse(status="error", error=...)`.
- Инструменты:
  - `read_doc_section`/`read_doc_pages`: валидируют обязательные аргументы, enforce `max_pages_per_call`, проверяют tenant по метаданным, возвращают текст и оценку tokens (`len(text)//4`), обрезают до `max_text_bytes`.
  - `read_doc_metadata`: отдаёт метаданные документа, проверяя tenant.
  - `doc_local_search`: ищет сниппеты в mock-контенте по query, обрезает каждый сниппет пропорционально `max_text_bytes`, возвращает count.
  - `list_available_tools`: возвращает список зарегистрированных инструментов.
- Mock DocumentRepository содержит один документ `doc_1` с секциями/контентом; используется, если `mock_mode=True` (значение по умолчанию).
- Rate limiter хранит счётчики в памяти процесса, без окна времени (накопительное количество вызовов/токенов).

## Что осталось сделать / отклонения от ТЗ
- Нет блоклист-фильтрации аргументов (`blocklist_keywords` из конфига не используется), нет ограничений на payload байты от клиента (только на отдаваемый текст).
- Rate limiting без временного окна; лимит на токены/вызовы накапливается навсегда до перезапуска, не соответствует «в минуту» из ТЗ.
- Mock_mode не влияет на инструменты (они всегда используют in-memory репозиторий), но нет явных статических ответов/метрик в стиле ТЗ; отсутствуют метрики/логирование вызовов и ошибок.
- Пользовательские роли/разрешения не проверяются, только совпадение tenant; нет блокировки по `blocklist_keywords`.
- Ограничения по страницам/байтам жёстко зашиты без динамических политик/tenant override; нет аудита/trace метрик.
