from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INGEST_", env_file=".env", extra="ignore")

    app_name: str = "ingestion-service"
    host: str = "0.0.0.0"
    port: int = 8050
    log_level: str = "info"

    storage_path: Path = Path("/var/lib/visior_ingestion_storage")
    mock_mode: bool = True

    doc_service_base_url: str | None = None

    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str | None = "us-east-1"
    s3_secure: bool = True
    local_storage_path: Path | None = Path("./.ingestion_storage")


@lru_cache
def get_settings() -> Settings:
    return Settings()
