from functools import lru_cache

from pydantic import Field
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
    window_radius: int | None = Field(
        default=None,
        ge=0,
        description="Per-side window radius (R); total chunks requested = 2R+1",
        env=["RAG_WINDOW_RADIUS", "ORCH_WINDOW_RADIUS"],
    )
    window_initial: int | None = Field(default=None, env="ORCH_WINDOW_INITIAL")
    window_step: int | None = Field(default=None, env="ORCH_WINDOW_STEP")
    window_max: int | None = Field(default=None, env="ORCH_WINDOW_MAX")
    legacy_total_window: int | None = Field(default=None, env="MCP_PROXY_MAX_CHUNK_WINDOW")
    retry_attempts: int = 1
    mock_mode: bool = True
    default_user_id: str = "anonymous"
    default_tenant_id: str = "observer_tenant"
    window_radius_baseline: int = 0

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        configured_radius = self.window_radius
        derived = self._derive_window_radius(configured_radius)
        self.window_radius = derived
        self.window_radius_baseline = derived
        # keep legacy knobs for compatibility but clamp to derived radius
        self.window_max = derived if self.window_max is None else min(self.window_max, derived)
        self.window_initial = (
            min(self.window_initial, derived) if self.window_initial is not None else (1 if derived > 0 else 0)
        )
        self.window_step = self.window_step if self.window_step is not None else 1

    def _derive_window_radius(self, configured_radius: int | None) -> int:
        """Unify legacy knobs into a single per-side radius."""
        candidates: list[int] = []
        if configured_radius is not None:
            candidates.append(max(0, configured_radius))
        if self.window_max is not None:
            candidates.append(max(0, self.window_max))
        if self.legacy_total_window is not None:
            # legacy limit was total (before+after+1); convert to per-side radius
            candidates.append(max(0, (self.legacy_total_window - 1) // 2))
        if candidates:
            return min(candidates)
        return 2  # sensible default aligned with a 5-chunk total window


@lru_cache
def get_settings() -> Settings:
    return Settings()
