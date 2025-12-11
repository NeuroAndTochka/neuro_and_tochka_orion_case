from contextlib import asynccontextmanager

from fastapi import FastAPI

from ingestion_service.config import get_settings
from ingestion_service.core.storage import InMemoryQueue
from ingestion_service.logging import configure_logging
from ingestion_service.routers import ingestion

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.queue = InMemoryQueue(settings)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(ingestion.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
