from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API Gateway."""

    model_config = SettingsConfigDict(env_prefix="API_GATEWAY_", env_file=".env", extra="ignore")

    app_name: str = "orion-api-gateway"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])

    safety_base_url: Optional[AnyHttpUrl] = None
    orchestrator_base_url: Optional[AnyHttpUrl] = None
    ingestion_base_url: Optional[AnyHttpUrl] = None
    documents_base_url: Optional[AnyHttpUrl] = None
    auth_introspection_url: Optional[AnyHttpUrl] = None

    auth_audience: Optional[str] = None
    auth_timeout_seconds: float = 5.0
    http_timeout_seconds: float = 10.0
    rate_limit_per_minute: int = 120
    mock_mode: bool = False
    # Force all UI traffic to the shared observer tenant to keep data consistent.
    default_tenant_id: str = "observer_tenant"


@lru_cache
def get_settings() -> Settings:
    return Settings()
