from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_gateway.config import get_settings
from api_gateway.core.middleware import RequestContextMiddleware
from api_gateway.logging import configure_logging
from api_gateway.routers import assistant, auth, documents, health

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    timeout = None if settings.http_timeout_seconds == 0 else settings.http_timeout_seconds
    async with httpx.AsyncClient(timeout=timeout) as client:
        app.state.http_client = client
        yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(assistant.router)
app.include_router(documents.router)
