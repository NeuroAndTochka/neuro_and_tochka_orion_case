# AI Orchestrator Skeleton

Implements the coordinator described in `docs/ai_orchestrator_spec.md`. The FastAPI service exposes `/internal/orchestrator/respond` to receive user queries, call Retrieval Service for section summaries, orchestrate tool-calling with MCP proxy using progressive window expansion, and return a structured answer with provenance.

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
| `ORCH_MCP_PROXY_URL` | – | MCP proxy execute endpoint |
| `ORCH_LLM_RUNTIME_URL` | – | URL for OpenAI-style runtime (tool calling) |
| `ORCH_DEFAULT_MODEL` | `gpt-4o-mini` | Model name for runtime |
| `ORCH_MODEL_STRATEGY` | `rag_mcp` | Controls prompt/flow strategy |
| `ORCH_PROMPT_TOKEN_BUDGET` | `4096` | Max tokens to send to LLM |
| `ORCH_CONTEXT_TOKEN_BUDGET` | `4096` | Max tokens accumulated from MCP results |
| `ORCH_MAX_TOOL_STEPS` | `4` | Tool-call loop limit |
| `ORCH_WINDOW_INITIAL` | `1` | Initial chunk window (before/after) |
| `ORCH_WINDOW_STEP` | `1` | Increment per repeated fetch |
| `ORCH_WINDOW_MAX` | `5` | Max window radius |
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
