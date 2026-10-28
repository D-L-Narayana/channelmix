from app.cache import Cache, build_cache
from app.config import get_settings

_cache: Cache | None = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = build_cache(get_settings().redis_url)
    return _cache


def set_cache(cache: Cache | None) -> None:
    """Used by tests to inject a fresh cache."""
    global _cache
    _cache = cache
