from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from openwebui_adapter.clients.gateway import GatewayClient
from openwebui_adapter.config import get_settings
from openwebui_adapter.logging import configure_logging
from openwebui_adapter.routers import openai

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    timeout = httpx.Timeout(None) if settings.http_timeout_seconds is None else settings.http_timeout_seconds
    async with httpx.AsyncClient(base_url=settings.gateway_base_url, timeout=timeout) as client:
        app.state.gateway_client = GatewayClient(settings, client)
        app.state.settings = settings
        yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(openai.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
