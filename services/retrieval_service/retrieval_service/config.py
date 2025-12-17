from functools import lru_cache

from pydantic import Field
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
    docs_top_k: int | None = Field(default=None, ge=1)
    sections_top_k_per_doc: int | None = Field(default=None, ge=1)
    max_total_sections: int | None = Field(default=None, ge=1)
    chunk_top_k: int = 20
    enable_filters: bool = False
    min_docs: int = 5
    rerank_score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    enable_section_cosine: bool = True
    enable_rerank: bool | None = None
    chunks_enabled: bool = False
    window_radius: int | None = Field(default=None, ge=0, env=["RAG_WINDOW_RADIUS", "RETR_WINDOW_RADIUS"])

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

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        self.docs_top_k = max(1, self.docs_top_k or self.doc_top_k)
        self.doc_top_k = self.docs_top_k
        self.sections_top_k_per_doc = max(1, self.sections_top_k_per_doc or self.section_top_k)
        self.section_top_k = self.sections_top_k_per_doc
        self.max_total_sections = max(
            1, self.max_total_sections or self.sections_top_k_per_doc or self.section_top_k
        )
        self.enable_rerank = self.enable_rerank if self.enable_rerank is not None else bool(self.rerank_enabled)
        self.rerank_score_threshold = min(1.0, max(0.0, float(self.rerank_score_threshold or 0.0)))


@lru_cache
def get_settings() -> Settings:
    return Settings()
