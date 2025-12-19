# Retrieval Service Skeleton

Implements the document/section/chunk search API described in `docs/retrieval_service_spec.md`. Provides `/internal/retrieval/search` (docs → sections → chunks) and `/internal/retrieval/chunks/window` (anchor + neighbors) with tenant isolation.

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
| `RETR_TOPK_PER_DOC` | `0` | Max chunks per doc (0 = no limit) |
| `RETR_MIN_SCORE` | – | Min score threshold |
| `RETR_DOC_TOP_K` | `5` | Top docs per query |
| `RETR_SECTION_TOP_K` | `10` | Top sections per doc set |
| `RETR_CHUNK_TOP_K` | `20` | Top chunks (if used) |
| `RETR_MIN_DOCS` | `5` | Minimum docs to return (padded by metadata fallback) |
| `RETR_VECTOR_BACKEND` | `chroma` | Backend type |
| `RETR_CHROMA_PATH` / `RETR_CHROMA_HOST` | `./.chroma_ingestion` / – | Chroma config (host for server, path for persistent) |
| `RETR_CHROMA_COLLECTION` | `ingestion_chunks` | Collection name |
| `RETR_EMBEDDING_API_BASE` / `RETR_EMBEDDING_API_KEY` | – | Endpoint/key for query embeddings (OpenAI-style) |
| `RETR_EMBEDDING_MODEL` | `baai/bge-m3` | Model name |
| `RETR_EMBEDDING_MAX_ATTEMPTS` / `RETR_EMBEDDING_RETRY_DELAY_SECONDS` | `2` / `1.0` | Retry settings |

## Tests

```bash
cd services/retrieval_service
./run_tests.sh
```
