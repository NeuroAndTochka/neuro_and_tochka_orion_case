from contextlib import asynccontextmanager

from fastapi import FastAPI

from document_service.config import get_settings
from document_service.core.repository import InMemoryRepository
from document_service.logging import configure_logging
from document_service.routers import documents

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.repository = InMemoryRepository()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(documents.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
