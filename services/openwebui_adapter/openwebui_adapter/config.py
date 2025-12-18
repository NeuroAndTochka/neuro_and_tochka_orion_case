from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADAPTER_", env_file=".env", extra="ignore", populate_by_name=True)

    app_name: str = "openwebui-adapter"
    host: str = "0.0.0.0"
    port: int = 8093
    log_level: str = "info"

    gateway_base_url: str = "http://api_gateway:8080"
    gateway_assistant_path: str = "/api/v1/assistant/query"
    auth_mode: Literal["passthrough", "static_token"] = "passthrough"
    static_bearer_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STATIC_BEARER_TOKEN", "ADAPTER_STATIC_BEARER_TOKEN"),
    )

    default_model_id: str = "orion-rag"
    default_language: str = "ru"
    http_timeout_seconds: float | None = None
    stream_chunk_chars: int = Field(default=400, ge=1, le=4000)
    max_prefix_chars: int = Field(default=2000, ge=200)

    openai_base_url: HttpUrl | None = Field(default=None, description="Optional external base override for docs/samples")


@lru_cache
def get_settings() -> Settings:
    return Settings()
