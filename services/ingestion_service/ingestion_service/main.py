from contextlib import asynccontextmanager

from fastapi import FastAPI

from ingestion_service.config import get_settings
from ingestion_service.core.embedding import EmbeddingClient
from ingestion_service.core.jobs import JobStore
from ingestion_service.core.storage import StorageClient
from ingestion_service.core.vector_store import VectorStore
from ingestion_service.logging import configure_logging
from ingestion_service.routers import ingestion

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.jobs = JobStore(redis_url=settings.redis_url)
    app.state.storage = StorageClient(settings)
    app.state.settings = settings
    app.state.embedding_client = EmbeddingClient(settings)
    app.state.vector_store = VectorStore(path=str(settings.chroma_path), enabled=not settings.mock_mode)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(ingestion.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
