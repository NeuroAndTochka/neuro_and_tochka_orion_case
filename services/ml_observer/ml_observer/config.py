from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OBS_", env_file=".env", extra="ignore")

    app_name: str = "ml-observer"
    host: str = "0.0.0.0"
    port: int = 8085
    log_level: str = "info"

    mock_mode: bool = True
    allowed_tenant: str = "observer_tenant"

    db_dsn: str = "sqlite+aiosqlite:///./ml_observer.db"

    ingestion_base_url: Optional[str] = None
    document_base_url: Optional[str] = None
    retrieval_base_url: Optional[str] = None
    llm_base_url: Optional[str] = None

    minio_endpoint: Optional[str] = None
    minio_bucket: Optional[str] = None
    minio_access_key: Optional[str] = None
    minio_secret_key: Optional[str] = None
    minio_secure: bool = True
    local_storage_path: Optional[Path] = Path("./.observer_storage")


@lru_cache
def get_settings() -> Settings:
    return Settings()
