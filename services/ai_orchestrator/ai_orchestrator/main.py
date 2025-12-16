from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from ai_orchestrator.config import get_settings
from ai_orchestrator.core.orchestrator import Orchestrator
from ai_orchestrator.logging import configure_logging
from ai_orchestrator.routers import orchestrator

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Upstream LLM/retrieval calls may be slow; bump client timeout to avoid premature failures.
    async with httpx.AsyncClient(timeout=60) as client:
        app.state.orchestrator = Orchestrator(settings, client)
        app.state.settings = settings
        yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(orchestrator.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
