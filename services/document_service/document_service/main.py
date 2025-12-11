from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from document_service.config import Settings, get_settings
from document_service.db import create_engine, create_session_factory, init_db
from document_service.logging import configure_logging, get_logger
from document_service.routers import documents
from document_service.storage import StorageClient

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


def ensure_runtime_configuration(current: Settings) -> None:
    if current.mock_mode:
        return
    missing: list[str] = []
    if not current.db_dsn or current.db_dsn.startswith("sqlite"):
        missing.append("DOC_DB_DSN (PostgreSQL DSN required in prod)")
    if not current.s3_bucket:
        missing.append("DOC_S3_BUCKET")
    if not current.s3_access_key:
        missing.append("DOC_S3_ACCESS_KEY")
    if not current.s3_secret_key:
        missing.append("DOC_S3_SECRET_KEY")
    if missing:
        raise RuntimeError(
            "Production mode requires external services. Missing configuration: " + ", ".join(missing)
        )


ensure_runtime_configuration(settings)

engine = create_engine(settings.db_dsn)
SessionLocal = create_session_factory(engine)
local_storage_path = settings.local_storage_path if settings.mock_mode else None
storage_client = StorageClient(
    bucket=settings.s3_bucket,
    endpoint=settings.s3_endpoint,
    access_key=settings.s3_access_key,
    secret_key=settings.s3_secret_key,
    region=settings.s3_region,
    secure=settings.s3_secure,
    local_storage_path=local_storage_path,
    default_expiry=settings.download_url_expiry_seconds,
)

logger.info(
    "document_service_configuration",
    mock_mode=settings.mock_mode,
    db_backend="sqlite" if settings.db_dsn.startswith("sqlite") else "postgres",
    has_s3=bool(settings.s3_bucket),
    local_storage=bool(local_storage_path),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(engine)
    app.state.session_factory = SessionLocal
    app.state.storage_client = storage_client
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(documents.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
