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
    redis_url: str | None = "redis://redis:6379/0"

    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str | None = "us-east-1"
    s3_secure: bool = True
    local_storage_path: Path | None = Path("./.ingestion_storage")

    embedding_api_base: str | None = None  # OpenAI-compatible endpoint (например, https://openrouter.ai/api/v1)
    embedding_api_key: str | None = None
    embedding_model: str = "baai/bge-m3"

    summary_api_base: str | None = None  # OpenAI-compatible endpoint для суммаризации
    summary_api_key: str | None = None
    summary_model: str = "openai/gpt-4o-mini"
    summary_referer: str | None = None
    summary_title: str | None = None

    retrieval_base_url: str | None = None

    max_pages: int = 2000
    max_file_mb: int = 50
    chunk_size: int = 2048
    chunk_overlap: int = 200

    chroma_path: Path = Path("./.chroma_ingestion")


@lru_cache
def get_settings() -> Settings:
    return Settings()
