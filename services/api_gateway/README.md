# API Gateway Skeleton

FastAPI-based API gateway skeleton for the Orion Visior project. Implements auth, assistant routing, document management, safety checks, rate limiting, and tracing hooks that mirror the production flow described in `docs/api_gatewat.md`.

## Quick start

```bash
cd services/api_gateway
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn api_gateway.main:app --reload
```

The service exposes the following public endpoints:

- `GET /api/v1/health`
- `GET /api/v1/auth/me`
- `POST /api/v1/assistant/query`
- `POST /api/v1/documents/upload`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{doc_id}`

Each public call enforces bearer authentication, per-tenant/user rate limiting, trace propagation, and downstream invocations to Safety/Orchestrator/Ingestion/Documents services.

## Configuration

All settings can be provided via environment variables prefixed with `API_GATEWAY_`. Key values:

| Variable | Default | Description |
| --- | --- | --- |
| `API_GATEWAY_HOST` | `0.0.0.0` | Bind host passed to uvicorn |
| `API_GATEWAY_PORT` | `8080` | Bind port |
| `API_GATEWAY_ALLOWED_ORIGINS` | `*` | CSV of origins for CORS |
| `API_GATEWAY_SAFETY_BASE_URL` | – | Safety service URL (`https://safety/...`) |
| `API_GATEWAY_ORCHESTRATOR_BASE_URL` | – | AI Orchestrator URL |
| `API_GATEWAY_INGESTION_BASE_URL` | – | Ingestion service URL |
| `API_GATEWAY_DOCUMENTS_BASE_URL` | – | Document service URL |
| `API_GATEWAY_AUTH_INTROSPECTION_URL` | – | OAuth2 introspection endpoint |
| `API_GATEWAY_AUTH_AUDIENCE` | – | Optional resource audience |
| `API_GATEWAY_RATE_LIMIT_PER_MINUTE` | `120` | Simple in-memory per user/tenant limit |
| `API_GATEWAY_MOCK_MODE` | `false` | When `true`, downstream calls are mocked for local development |

`mock_mode` allows the gateway to run standalone while still enforcing headers, safety filtering, and rate limiting logic.

## Downstream interactions

All outbound calls automatically include:

- `X-Request-ID` propagated trace identifier
- `X-Tenant-ID` taken from the authenticated user or upstream header
- `X-User-ID` and `X-User-Roles`

Failed downstream requests are normalized into FastAPI HTTP errors so the frontend always receives the error shape defined in `docs/api_docs.md`.

## Tests

Unit and integration tests live under `services/api_gateway/tests`. Run them via:

```bash
cd services/api_gateway
./run_tests.sh
```

Pass additional args (e.g., `./run_tests.sh -k assistant`) to filter pytest cases.

## Docker

```bash
cd services/api_gateway
docker build -t visior-api-gateway .
docker run --rm -p 8080:8080 visior-api-gateway
```
