# Retrieval Service Skeleton

Implements the document/section/chunk search API described in `docs/retrieval_service_spec.md`. Provides `/internal/retrieval/search` to return doc/section/chunk hits with tenant isolation and token budgeting hints.

## Quick start

```bash
cd services/retrieval_service
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn retrieval_service.main:app --reload
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `RETR_HOST` | `0.0.0.0` | Bind host |
| `RETR_PORT` | `8040` | Bind port |
| `RETR_LOG_LEVEL` | `info` | Logging level |
| `RETR_MOCK_MODE` | `true` | In-memory index |
| `RETR_MAX_RESULTS` | `5` | Cap results count |

## Tests

```bash
cd services/retrieval_service
./run_tests.sh
```
