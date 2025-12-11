from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INGEST_", env_file=".env", extra="ignore")

    app_name: str = "ingestion-service"
    host: str = "0.0.0.0"
    port: int = 8050
    log_level: str = "info"

    storage_path: Path = Path("./storage")
    mock_mode: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
