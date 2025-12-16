# Safety Service Skeleton

FastAPI service that implements the input/output safety guards described in `docs/safety_service_spec.md`. It offers `/internal/safety/input-check` and `/internal/safety/output-check` endpoints, applying lightweight heuristics (keyword blocklists, regex-based PII detection, and configurable policy levels) to mimic the production behavior.

## Quick start

```bash
cd services/safety_service
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn safety_service.main:app --reload
```

## Configuration

Environment variables prefixed with `SAFETY_SERVICE_` configure runtime behavior:

| Variable | Default | Description |
| --- | --- | --- |
| `SAFETY_SERVICE_HOST` | `0.0.0.0` | Bind host |
| `SAFETY_SERVICE_PORT` | `8081` | Bind port |
| `SAFETY_SERVICE_LOG_LEVEL` | `info` | Logging level |
| `SAFETY_SERVICE_POLICY_MODE` | `balanced` | `strict`, `balanced`, or `relaxed` sensitivity |
| `SAFETY_SERVICE_BLOCKLIST` | `hack,breach,exploit` | Comma-separated disallowed keywords |
| `SAFETY_SERVICE_ENABLE_PII_SANITIZE` | `true` | Whether to redact detected PII in `transformed` responses |
| `SAFETY_SERVICE_DEFAULT_POLICY_ID` | `policy_default_v1` | Policy identifier added to responses |
| `SAFETY_SERVICE_SAFETY_LLM_ENABLED` | `false` | Enable OpenAI-based safety review |
| `SAFETY_SERVICE_SAFETY_LLM_API_KEY` | - | API key for the OpenAI-compatible endpoint |
| `SAFETY_SERVICE_SAFETY_LLM_BASE_URL` | - | Override API base (e.g., OpenRouter) |
| `SAFETY_SERVICE_SAFETY_LLM_MODEL` | `openai/gpt-oss-safeguard-20b` | Safety model identifier |
| `SAFETY_SERVICE_SAFETY_LLM_TIMEOUT` | `15.0` | Timeout (seconds) for the LLM call |
| `SAFETY_SERVICE_SAFETY_LLM_FAIL_OPEN` | `true` | When `false`, guard failures block the query |

## Tests

```bash
cd services/safety_service
./run_tests.sh
```

Pass pytest flags through the helper script to target individual scenarios (e.g., `./run_tests.sh -k input`).

## Docker

```bash
cd services/safety_service
docker build -t visior-safety-service .
docker run --rm -p 8081:8081 visior-safety-service
```
