# Document Service Skeleton

Provides the metadata API described in `docs/document_service_spec.md`. Handles document listings, detail lookups, section metadata, and ingestion status updates with tenant isolation enforced at the API layer.

## Quick start

```bash
cd services/document_service
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn document_service.main:app --reload
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `DOC_HOST` | `0.0.0.0` | Bind host |
| `DOC_PORT` | `8060` | Bind port |
| `DOC_LOG_LEVEL` | `info` | Logging level |
| `DOC_MOCK_MODE` | `true` | Use in-memory store |
| `DOC_DB_DSN` | – | PostgreSQL DSN (future) |
| `DOC_CACHE_URL` | – | Redis cache (future) |

## Tests

```bash
cd services/document_service
./run_tests.sh
```

## Docker

```bash
cd services/document_service
docker build -t visior-document-service .
docker run --rm -p 8060:8060 visior-document-service
```
