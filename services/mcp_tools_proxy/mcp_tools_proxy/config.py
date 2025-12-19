from functools import lru_cache
from typing import List

from pydantic import Field
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
    retrieval_window_url: str | None = None
    retrieval_timeout: float = 5.0
    max_window_radius: int | None = Field(
        default=None,
        ge=0,
        env=["RAG_WINDOW_RADIUS", "MCP_PROXY_MAX_WINDOW_RADIUS"],
        description="Per-side window radius (R). Total chunks requested = 2R+1.",
    )
    max_chunk_window: int | None = Field(default=None, env="MCP_PROXY_MAX_CHUNK_WINDOW")
    max_window_radius_source: str = "default"

    blocklist_keywords: List[str] = ["leak", "dump", "exfiltrate"]

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        configured_radius = self.max_window_radius
        derived = self._derive_radius(configured_radius)
        self.max_window_radius = derived

    def _derive_radius(self, configured_radius: int | None) -> int:
        candidates: list[tuple[int, str]] = []
        if configured_radius is not None:
            candidates.append((max(0, configured_radius), "settings.max_window_radius"))
        if self.max_chunk_window is not None:
            candidates.append((max(0, (self.max_chunk_window - 1) // 2), "settings.max_chunk_window (legacy total)"))
        if candidates:
            chosen_value, chosen_source = min(candidates, key=lambda item: item[0])
            self.max_window_radius_source = chosen_source
            return chosen_value
        self.max_window_radius_source = "default"
        return 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
