# Ingestion Service Skeleton

Handles document uploads, parsing orchestration, and status callbacks as described in `docs/document_service_spec.md` (ingestion pipeline). Provides `/internal/ingestion/enqueue` for API Gateway uploads and `/internal/ingestion/status` for status updates/callbacks.

## Quick start

```bash
cd services/ingestion_service
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn ingestion_service.main:app --reload
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `INGEST_HOST` | `0.0.0.0` | Bind host |
| `INGEST_PORT` | `8050` | Bind port |
| `INGEST_LOG_LEVEL` | `info` | Logging level |
| `INGEST_STORAGE_PATH` | `./storage` | Where uploaded files land (mock) |
| `INGEST_MOCK_MODE` | `true` | Skip external parsers/pipelines |

## Tests

```bash
cd services/ingestion_service
./run_tests.sh
```
