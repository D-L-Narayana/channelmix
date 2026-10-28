import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ChannelMix API"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./channelmix.db"
    # NullPool is what you want behind a transaction pooler (Supabase 6543 / PgBouncer) and on serverless.
    # Auto-enabled on Vercel; set DB_POOL=null|queue to force.
    db_pool: str = "null" if os.environ.get("VERCEL") else "queue"
    redis_url: str | None = None
    cache_ttl_seconds: int = 300
    cache_max_entries: int = 2048
    log_level: str = "INFO"
    cors_origins: str = "https://channelmix.vercel.app,http://localhost:5173"
    # SSE: close the response after this many seconds (Vercel function limit) so EventSource reconnects
    sse_max_seconds: float = 25.0
    sse_heartbeat_seconds: float = 15.0
    sse_poll_seconds: float = 1.0
    public_web_url: str = "https://channelmix.vercel.app"
    # Abuse limits (self-serve signup is public)
    signup_per_ip_per_hour: int = 5
    signup_global_per_hour: int = 60
    max_workspaces: int = 2000
    max_metric_rows_per_workspace: int = 500_000


@lru_cache
def get_settings() -> Settings:
    return Settings()
