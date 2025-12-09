from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_SERVICE_", env_file=".env", extra="ignore")

    app_name: str = "llm-service"
    host: str = "0.0.0.0"
    port: int = 8090
    log_level: str = "info"

    llm_runtime_url: str | None = None
    default_model: str = "mock-model"
    max_tool_steps: int = 3
    max_prompt_tokens: int = 4096
    max_completion_tokens: int = 512
    enable_json_mode: bool = True
    mcp_proxy_url: str | None = None
    mock_mode: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
