# AI Orchestrator Skeleton

Implements the coordinator described in `docs/ai_orchestrator_spec.md`. The FastAPI service exposes `/internal/orchestrator/respond` to receive user queries, call Retrieval Service, forward context to LLM Service, pass outputs through Safety Service, and return a final structured answer.

## Quick start

```bash
cd services/ai_orchestrator
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn ai_orchestrator.main:app --reload
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `ORCH_HOST` | `0.0.0.0` | Bind host |
| `ORCH_PORT` | `8070` | Bind port |
| `ORCH_LOG_LEVEL` | `info` | Logging level |
| `ORCH_RETRIEVAL_URL` | – | Base URL of Retrieval Service |
| `ORCH_LLM_URL` | – | URL for `POST /internal/llm/generate` |
| `ORCH_SAFETY_URL` | – | URL for `POST /internal/safety/output-check` |
| `ORCH_MODEL_STRATEGY` | `rag_default` | Controls prompt/flow strategy |
| `ORCH_PROMPT_TOKEN_BUDGET` | `4096` | Max tokens to send to LLM |
| `ORCH_RETRY_ATTEMPTS` | `1` | Retries for transient errors |
| `ORCH_MOCK_MODE` | `true` | Use in-memory mocks for Retrieval/LLM/Safety |

## Tests

```bash
cd services/ai_orchestrator
./run_tests.sh
```

Filter with `./run_tests.sh -k respond` to target specific flows.

## Docker

```bash
cd services/ai_orchestrator
docker build -t visior-ai-orchestrator .
docker run --rm -p 8070:8070 visior-ai-orchestrator
```
