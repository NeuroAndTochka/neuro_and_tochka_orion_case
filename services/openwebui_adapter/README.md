# Open WebUI Adapter

OpenAI-compatible shim that forwards `/v1/models` and `/v1/chat/completions` calls from Open WebUI to Orion API Gateway (`POST /api/v1/assistant/query`). It preserves trace IDs for log correlation and keeps payloads compatible with OpenAI clients.

## Quick start

```bash
cd services/openwebui_adapter
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn openwebui_adapter.main:app --reload --port 8093
```

The adapter expects the Gateway to be reachable at `GATEWAY_BASE_URL` (defaults to `http://api_gateway:8080` in compose).

## Configuration

Environment variables (prefix `ADAPTER_`):

| Variable | Default | Description |
| --- | --- | --- |
| `ADAPTER_HOST` | `0.0.0.0` | Bind host |
| `ADAPTER_PORT` | `8093` | Bind port |
| `ADAPTER_LOG_LEVEL` | `info` | Logging verbosity |
| `ADAPTER_GATEWAY_BASE_URL` | `http://api_gateway:8080` | API Gateway base URL |
| `ADAPTER_GATEWAY_ASSISTANT_PATH` | `/api/v1/assistant/query` | Assistant endpoint path |
| `ADAPTER_AUTH_MODE` | `passthrough` | `passthrough` forwards inbound `Authorization`, `static_token` uses `STATIC_BEARER_TOKEN` |
| `STATIC_BEARER_TOKEN` | – | Token used when `AUTH_MODE=static_token` |
| `ADAPTER_DEFAULT_MODEL_ID` | `orion-rag` | Model name exposed to Open WebUI |
| `ADAPTER_DEFAULT_LANGUAGE` | `ru` | Default language sent to Gateway |
| `ADAPTER_HTTP_TIMEOUT_SECONDS` | `30` | Upstream HTTP timeout |
| `ADAPTER_STREAM_CHUNK_CHARS` | `400` | Chunk size for streaming responses |
| `ADAPTER_MAX_PREFIX_CHARS` | `2000` | Max size for system/context prefix in query |

## Endpoints and examples

List models:

```bash
curl -s http://localhost:8093/v1/models
```

Chat completion (non-streaming):

```bash
curl -i http://localhost:8093/v1/chat/completions \
  -H "Authorization: Bearer $GATEWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "orion-rag",
    "messages": [{"role": "user", "content": "Привет!"}]
  }'
# X-Trace-Id header mirrors Gateway meta.trace_id for log correlation
```

Streaming example:

```bash
curl -N http://localhost:8093/v1/chat/completions \
  -H "Authorization: Bearer $GATEWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "orion-rag",
    "stream": true,
    "messages": [{"role": "user", "content": "Что нового?"}]
  }'
```

## Docker / Compose

`docker-compose.yml` now includes `openwebui_adapter` and `open-webui` services. Launch the full stack:

```bash
docker compose up --build
```

Open WebUI will reach the adapter via `OPENAI_API_BASE_URL=http://openwebui_adapter:8093/v1` on the shared `visior` network. Persisted data lives in the `openwebui-data` volume.

To override API keys or static tokens, create a `.env` or `docker-compose.override.yml` with your secrets; they are not baked into the default compose file.
