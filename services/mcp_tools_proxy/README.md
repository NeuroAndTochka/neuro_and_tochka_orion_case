# MCP Tools Proxy Skeleton

Implements the Model Context Protocol tool executor described in `docs/mcp_tools_proxy_spec.md`. The FastAPI service exposes `/internal/mcp/execute` for single tool-calls and `/health` for heartbeat. Each tool enforces tenant isolation, token/page limits, and rate limits before returning sanitized snippets back to the LLM service.

## Quick start

```bash
cd services/mcp_tools_proxy
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn mcp_tools_proxy.main:app --reload
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `MCP_PROXY_HOST` | `0.0.0.0` | Bind host |
| `MCP_PROXY_PORT` | `8082` | Bind port |
| `MCP_PROXY_LOG_LEVEL` | `info` | Logging level |
| `MCP_PROXY_MAX_PAGES_PER_CALL` | `5` | Hard limit for `read_doc_pages` |
| `MCP_PROXY_MAX_TEXT_BYTES` | `20480` | Limit per response (≈20 KB) |
| `MCP_PROXY_RATE_LIMIT_CALLS` | `10` | Calls per doc & generation |
| `MCP_PROXY_RATE_LIMIT_TOKENS` | `2000` | Approx token budget per response |
| `MCP_PROXY_MOCK_MODE` | `true` | Use in-memory repositories instead of real stores |

Set `MCP_PROXY_MOCK_MODE=false` and wire actual repositories/clients when backends are available.

## Tests

```bash
cd services/mcp_tools_proxy
./run_tests.sh
```

Use pytest flags through the helper script to target specific tools, e.g. `./run_tests.sh -k read_doc_section`.
