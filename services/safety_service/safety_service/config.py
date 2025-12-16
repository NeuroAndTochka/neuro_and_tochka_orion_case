from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAFETY_SERVICE_", env_file=".env", extra="ignore")

    app_name: str = "safety-service"
    host: str = "0.0.0.0"
    port: int = 8081
    log_level: str = "info"

    policy_mode: str = "balanced"  # strict / balanced / relaxed
    blocklist: List[str] = ["hack", "breach", "exploit"]
    enable_pii_sanitize: bool = True
    default_policy_id: str = "policy_default_v1"
    safety_llm_enabled: bool = False
    safety_llm_model: str = "openai/gpt-oss-safeguard-20b"
    safety_llm_base_url: Optional[str] = None
    safety_llm_api_key: Optional[str] = None
    safety_llm_timeout: float = 15.0
    safety_llm_fail_open: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
