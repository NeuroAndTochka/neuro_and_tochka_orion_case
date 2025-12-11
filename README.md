# neuro_and_tochka_orion_case

## Running services locally with Docker

Each microservice has its own `Dockerfile` under `services/<service_name>`. To build and run all skeleton services together:

```bash
docker compose up --build
```

This starts:

- API Gateway on `http://localhost:8080`
- Safety Service on `http://localhost:8081`
- MCP Tools Proxy on `http://localhost:8082`
- LLM Service on `http://localhost:8090`
- AI Orchestrator on `http://localhost:8070`
- Document Service on `http://localhost:8060`
- Ingestion Service on `http://localhost:8050`
- Retrieval Service on `http://localhost:8040`

Stop everything with `docker compose down`. Use `docker compose up --build api_gateway` (or another service name) to rebuild/run individually.

## Инструменты качества

### Pre-commit и Flake8
Мы используем [pre-commit](https://pre-commit.com/) для локального запуска `flake8` и базовых хуков форматирования.

```bash
pip install pre-commit
pre-commit install           # ставит git-хуки
pre-commit run --all-files   # запустить проверки вручную
```

Файл конфигурации — `.pre-commit-config.yaml`, правила линтера описаны в `.flake8`.

### CI
Каждый push и pull request к `main` запускает workflow `.github/workflows/ci.yml`. Он:

1. Устанавливает Python 3.10 и все сервисы в editable-режиме с dev-зависимостями.
2. Запускает `pre-commit run --all-files` (то же, что и локальный flake8).
3. Выполняет `pytest`, что покрывает юнит- и интеграционные тесты.

Перед созданием PR желательно выполнить `pre-commit run --all-files` и `pytest` локально для более быстрого review.
