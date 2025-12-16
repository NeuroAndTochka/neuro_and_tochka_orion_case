from contextlib import asynccontextmanager
import asyncio
import structlog

from fastapi import FastAPI

from ingestion_service.config import Settings, get_settings
from ingestion_service.core.embedding import EmbeddingClient
from ingestion_service.core.jobs import JobStore
from ingestion_service.core.queue import IngestionQueue, WorkItem
from ingestion_service.core.summarizer import Summarizer
from ingestion_service.core.storage import StorageClient
from ingestion_service.core.vector_store import VectorStore
from ingestion_service.core.pipeline import process_file
from ingestion_service.logging import configure_logging
from ingestion_service.routers import ingestion

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


def ensure_runtime_configuration(current: Settings) -> None:
    if current.mock_mode:
        return
    missing: list[str] = []
    if not current.doc_service_base_url:
        missing.append("INGEST_DOC_SERVICE_BASE_URL")
    if not (current.s3_bucket and current.s3_access_key and current.s3_secret_key):
        missing.append("S3 configuration (INGEST_S3_BUCKET/ACCESS_KEY/SECRET_KEY)")
    if not (current.embedding_api_base and current.embedding_api_key):
        missing.append("Embedding endpoint/key (INGEST_EMBEDDING_API_BASE/KEY)")
    if not (current.summary_api_base and current.summary_api_key):
        missing.append("Summary endpoint/key (INGEST_SUMMARY_API_BASE/KEY)")
    if missing:
        raise RuntimeError("Production mode requires external services: " + ", ".join(missing))


ensure_runtime_configuration(settings)
logger.info(
    "ingestion_configuration",
    mock_mode=settings.mock_mode,
    has_doc_service=bool(settings.doc_service_base_url),
    has_s3=bool(settings.s3_bucket),
    has_embedding_endpoint=bool(settings.embedding_api_base),
    has_summary_endpoint=bool(settings.summary_api_base),
    redis_enabled=bool(settings.redis_url),
    worker_count=settings.worker_count,
    queue_name=settings.queue_name,
)


async def worker_loop(app: FastAPI) -> None:
    queue: IngestionQueue = app.state.queue
    jobs: JobStore = app.state.jobs
    storage: StorageClient = app.state.storage
    embedding: EmbeddingClient = app.state.embedding_client
    summarizer: Summarizer = app.state.summarizer
    vector_store: VectorStore = app.state.vector_store
    settings: Settings = app.state.settings
    while True:
        item = await queue.pop(timeout=5)
        if not item:
            continue
        ticket = jobs.get(item.job_id)
        if not ticket:
            logger.warning("ingestion_queue_skip_missing_job", job_id=item.job_id)
            continue
        success = process_file(
            ticket=ticket,
            storage=storage,
            embedding=embedding,
            summarizer=summarizer,
            jobs=jobs,
            doc_service_base_url=settings.doc_service_base_url,
            max_pages=settings.max_pages,
            max_file_mb=settings.max_file_mb,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            vector_store=vector_store,
            product=item.product,
            version=item.version,
            tags=item.tags,
        )
        if not success and item.attempt < settings.max_attempts:
            next_attempt = item.attempt + 1
            logger.warning(
                "ingestion_retry_scheduled",
                job_id=item.job_id,
                attempt=next_attempt,
            )
            await asyncio.sleep(settings.retry_delay_seconds)
            await queue.enqueue(
                WorkItem(
                    job_id=item.job_id,
                    tenant_id=item.tenant_id,
                    doc_id=item.doc_id,
                    storage_uri=item.storage_uri,
                    product=item.product,
                    version=item.version,
                    tags=item.tags,
                    attempt=next_attempt,
                )
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.jobs = JobStore(redis_url=settings.redis_url)
    app.state.storage = StorageClient(settings)
    app.state.settings = settings
    app.state.embedding_client = EmbeddingClient(settings)
    app.state.summarizer = Summarizer(settings)
    app.state.vector_store = VectorStore(
        path=str(settings.chroma_path),
        host=str(settings.chroma_host) if settings.chroma_host else None,
        enabled=not settings.mock_mode,
    )
    app.state.queue = IngestionQueue(settings.redis_url, settings.queue_name)
    app.state.worker_tasks: list[asyncio.Task] = []
    if settings.worker_count > 0:
        for _ in range(settings.worker_count):
            task = asyncio.create_task(worker_loop(app))
            app.state.worker_tasks.append(task)
    logger.info(
        "ingestion_service_started",
        mock_mode=settings.mock_mode,
        embedding_endpoint=settings.embedding_api_base,
        summary_endpoint=settings.summary_api_base,
        redis_enabled=bool(settings.redis_url),
        s3_enabled=bool(settings.s3_bucket),
        vector_store=not settings.mock_mode,
        worker_count=settings.worker_count,
    )
    yield
    for task in getattr(app.state, "worker_tasks", []):
        task.cancel()
    await asyncio.gather(*getattr(app.state, "worker_tasks", []), return_exceptions=True)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(ingestion.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
