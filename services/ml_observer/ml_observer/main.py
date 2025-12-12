from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ml_observer.config import Settings, get_settings
from ml_observer.db import create_engine, create_session_factory, init_db
from ml_observer.logging import configure_logging, get_logger
from ml_observer.routers import observer, ui

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


def ensure_runtime_configuration(current: Settings) -> None:
    if current.mock_mode:
        return
    missing: list[str] = []
    if not current.db_dsn or current.db_dsn.startswith("sqlite"):
        missing.append("OBS_DB_DSN (PostgreSQL DSN required in prod mode)")
    if missing:
        raise RuntimeError("Production mode requires external services: " + ", ".join(missing))


ensure_runtime_configuration(settings)

engine = create_engine(settings.db_dsn)
SessionLocal = create_session_factory(engine)

logger.info(
    "ml_observer_configuration",
    mock_mode=settings.mock_mode,
    db_backend="sqlite" if settings.db_dsn.startswith("sqlite") else "postgres",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(engine)
    app.state.session_factory = SessionLocal
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(observer.router)
app.include_router(ui.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
