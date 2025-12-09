# LLM Service Skeleton

Implements the orchestration layer described in `docs/llm_service_spec.md`. The service accepts `/internal/llm/generate` requests, assembles prompts with optional RAG chunks, simulates tool-call loops via MCP Tools Proxy, and produces structured answers with usage metadata.

## Quick start

```bash
cd services/llm_service
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn llm_service.main:app --reload
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `LLM_SERVICE_HOST` | `0.0.0.0` | Bind host |
| `LLM_SERVICE_PORT` | `8090` | Bind port |
| `LLM_SERVICE_LOG_LEVEL` | `info` | Logging level |
| `LLM_RUNTIME_URL` | – | Base URL of OpenAI-compatible runtime |
| `LLM_DEFAULT_MODEL` | `mock-model` | Model name when not specified |
| `LLM_MAX_TOOL_STEPS` | `3` | Maximum MCP tool iterations |
| `LLM_MAX_PROMPT_TOKENS` | `4096` | Prompt budget before trimming |
| `LLM_MAX_COMPLETION_TOKENS` | `512` | Generation budget |
| `LLM_MCP_PROXY_URL` | – | URL of MCP Tools Proxy |
| `LLM_ENABLE_JSON_MODE` | `true` | Force JSON/function-call responses |
| `LLM_MOCK_MODE` | `true` | Use in-process mock runtime & MCP client |

## Tests

```bash
cd services/llm_service
./run_tests.sh
```

Filter with `./run_tests.sh -k tool` to target MCP scenarios.

## Docker

```bash
cd services/llm_service
docker build -t visior-llm-service .
docker run --rm -p 8090:8090 visior-llm-service
```
