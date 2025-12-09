from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_PROXY_", env_file=".env", extra="ignore")

    app_name: str = "mcp-tools-proxy"
    host: str = "0.0.0.0"
    port: int = 8082
    log_level: str = "info"

    max_pages_per_call: int = 5
    max_text_bytes: int = 20_480
    rate_limit_calls: int = 10
    rate_limit_tokens: int = 2000
    mock_mode: bool = True

    blocklist_keywords: List[str] = ["leak", "dump", "exfiltrate"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
