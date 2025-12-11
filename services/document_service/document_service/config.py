from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOC_", env_file=".env", extra="ignore")

    app_name: str = "document-service"
    host: str = "0.0.0.0"
    port: int = 8060
    log_level: str = "info"

    mock_mode: bool = True
    db_dsn: str | None = None
    cache_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
