from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOC_", env_file=".env", extra="ignore")

    app_name: str = "document-service"
    host: str = "0.0.0.0"
    port: int = 8060
    log_level: str = "info"

    mock_mode: bool = True
    db_dsn: str = "sqlite+aiosqlite:///./document_service.db"
    cache_url: str | None = None

    s3_endpoint: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str | None = "us-east-1"
    s3_bucket: str | None = None
    s3_secure: bool = True
    local_storage_path: Path | None = Path("./.document_storage")
    download_url_expiry_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
