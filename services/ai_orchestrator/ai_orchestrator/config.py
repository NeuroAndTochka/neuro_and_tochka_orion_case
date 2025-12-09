from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORCH_", env_file=".env", extra="ignore")

    app_name: str = "ai-orchestrator"
    host: str = "0.0.0.0"
    port: int = 8070
    log_level: str = "info"

    retrieval_url: str | None = None
    llm_url: str | None = None
    safety_url: str | None = None
    model_strategy: str = "rag_default"
    prompt_token_budget: int = 4096
    retry_attempts: int = 1
    mock_mode: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
