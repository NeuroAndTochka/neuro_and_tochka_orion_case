from fastapi import FastAPI

from retrieval_service.config import get_settings
from retrieval_service.logging import configure_logging
from retrieval_service.routers import retrieval

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)
app.include_router(retrieval.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
