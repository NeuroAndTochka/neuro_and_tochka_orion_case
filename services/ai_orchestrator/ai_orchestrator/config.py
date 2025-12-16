from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORCH_", env_file=".env", extra="ignore")

    app_name: str = "ai-orchestrator"
    host: str = "0.0.0.0"
    port: int = 8070
    log_level: str = "info"

    retrieval_url: str | None = None
    mcp_proxy_url: str | None = None
    llm_runtime_url: str | None = None
    llm_api_key: str | None = None
    default_model: str = "gpt-4o-mini"
    model_strategy: str = "rag_mcp"
    prompt_token_budget: int = 4096
    context_token_budget: int = 4096
    max_tool_steps: int = 4
    window_initial: int = 1
    window_step: int = 1
    window_max: int = 5
    retry_attempts: int = 1
    mock_mode: bool = True
    default_user_id: str = "anonymous"
    default_tenant_id: str = "observer_tenant"


@lru_cache
def get_settings() -> Settings:
    return Settings()
