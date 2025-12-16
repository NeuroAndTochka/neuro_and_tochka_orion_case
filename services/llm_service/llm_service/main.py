from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from llm_service.config import get_settings
from llm_service.core.orchestrator import LLMOrchestrator
from llm_service.logging import configure_logging
from llm_service.routers import llm

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        app.state.orchestrator = LLMOrchestrator(settings, client)
        app.state.settings = settings
        yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(llm.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
