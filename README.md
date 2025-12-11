# Orion Soft — Visior Backend

Моно-репозиторий для внутренних микросервисов ассистента Visior:

- API Gateway (edge-слой, безопасность, документы)
- Safety Service (input/output guard)
- AI Orchestrator (управление RAG-пайплайном)
- LLM Service (генерация, MCP)
- MCP Tools Proxy (инструменты доступа к контенту)
- Document / Ingestion / Retrieval service

Полезные спецификации и схемы лежат в `docs/`.

## Как запустить
Каждый сервис имеет свой `Dockerfile`. Для запуска всего стека:

```bash
docker compose up --build
```

Порты по умолчанию: API Gateway — `localhost:8080`, Safety — `8081`, MCP — `8082`, LLM — `8090`, Orchestrator — `8070`, Document — `8060`, Ingestion — `8050`, Retrieval — `8040`.

Остановить — `docker compose down`. Для перезапуска конкретного сервиса используйте `docker compose up --build <service_name>`.

## Код-стайл и проверки
- Питон: `flake8` + `flake8-bugbear`, конфиг `.flake8`.
- Автоматические проверки через `pre-commit` (end-of-file, trimming, flake8).
  ```bash
  pip install pre-commit
  pre-commit install
  pre-commit run --all-files
  ```
- Тесты: `pytest` в корне (покрывает все сервисы + E2E).

CI (`.github/workflows/ci.yml`) запускает:
1. Установку Python 3.10 + editable зависимостей всех сервисов.
2. `pre-commit run --all-files`.
3. `pytest`.

## Как собираются и устанавливаются сервисы
Каждый микросервис — самостоятельный Python-пакет с `pyproject.toml` в каталоге `services/<name>`. Для разработки используется editable-установка:

```bash
cd services/api_gateway
pip install -e .[dev]  # ставит runtime-зависимости + pytest/anyio
```

Повторите команду для остальных сервисов (`ai_orchestrator`, `llm_service`, `mcp_tools_proxy`, `safety_service`, `document_service`, `ingestion_service`, `retrieval_service`).
Editable-режим позволяет видеть изменения кода без повторной сборки пакета.

### Общий сценарий сборки
1. Устанавливаем системный Python 3.10+ и `pip install -r requirements.txt` **не требуется** — зависимости описаны в каждом `pyproject.toml`.
2. Для локальной разработки запускаем `pip install -e services/<name>[dev]`.
   Это устанавливает:
   - runtime-библиотеки (FastAPI, httpx, pydantic и т.д.);
   - dev-зависимости (pytest, anyio) из `[project.optional-dependencies].dev`.
3. Docker-образы собираются стандартно:
   ```bash
   docker compose build api_gateway   # или другой сервис
   ```
   Каждый Dockerfile внутри `services/<name>` копирует исходники, устанавливает зависимости и запускает Uvicorn.
4. Для CI/Prod можно использовать `pip install -e "services/<name>"` или `pip install services/<name>` после `python -m build`. GitHub Actions делает editable-установку всех сервисов перед тестами (см. `.github/workflows/ci.yml`).

Такой подход позволяет легко разворачивать конкретный сервис (например, `uvicorn api_gateway.main:app`) после установки зависимостей.

## Правила работы
1. Для любой новой фичи создаём отдельную ветку от `main` и работаем только в ней.
2. После реализации локально запускаем `pre-commit run --all-files` и `pytest`. PR без зелёных проверок не принимаются.
3. Создавая pull request, чётко описываем суть изменения (что сделано, зачем, какие тесты).
4. **Строго запрещено** самому аппрувить/мерджить собственные PR — всегда нужен независимый ревьюер.

Соблюдение этих правил гарантирует, что пайплайн остаётся стабильным, а изменения — прозрачными.
