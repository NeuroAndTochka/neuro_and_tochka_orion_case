from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RETR_", env_file=".env", extra="ignore")

    app_name: str = "retrieval-service"
    host: str = "0.0.0.0"
    port: int = 8040
    log_level: str = "info"

    mock_mode: bool = True
    max_results: int = 5
    topk_per_doc: int = 0
    min_score: float | None = None
    doc_top_k: int = 5
    section_top_k: int = 10
    chunk_top_k: int = 20
    enable_filters: bool = False
    min_docs: int = 5

    vector_backend: str = "chroma"
    chroma_path: str = "./.chroma_ingestion"
    chroma_host: str | None = None
    chroma_collection: str = "ingestion_chunks"

    embedding_api_base: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str = "baai/bge-m3"
    embedding_max_attempts: int = 2
    embedding_retry_delay_seconds: float = 1.0

    rerank_enabled: bool = False
    rerank_model: str = "gpt-4o-mini"
    rerank_api_base: str | None = None
    rerank_api_key: str | None = None
    rerank_top_n: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
