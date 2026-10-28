from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ChannelMix API"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./channelmix.db"
    redis_url: str | None = None
    cache_ttl_seconds: int = 300
    log_level: str = "INFO"
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
