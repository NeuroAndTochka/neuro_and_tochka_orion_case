from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RETR_", env_file=".env", extra="ignore")

    app_name: str = "retrieval-service"
    host: str = "0.0.0.0"
    port: int = 8040
    log_level: str = "info"

    mock_mode: bool = True
    max_results: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
