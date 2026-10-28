"""Report cache with per-account invalidation.

Keys are namespaced ``cm:{account_id}:{name}:{hash}`` and every key is also
recorded in a per-account index set ``cm:idx:{account_id}`` so invalidation is
an exact O(keys-for-account) delete instead of a SCAN over the whole keyspace.

Redis is used when ``REDIS_URL`` is configured; otherwise an in-process TTL
cache with the same interface is used (local dev / tests).
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any, Protocol

log = logging.getLogger("channelmix.cache")


class Cache(Protocol):
    backend: str

    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl: int, account_id: int) -> None: ...
    def invalidate_account(self, account_id: int) -> int: ...
    def clear(self) -> None: ...


def make_key(account_id: int, name: str, params: dict[str, Any]) -> str:
    digest = hashlib.sha1(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return f"cm:{account_id}:{name}:{digest}"


def _index_key(account_id: int) -> str:
    return f"cm:idx:{account_id}"


class InMemoryCache:
    backend = "memory"

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}
        self._index: dict[int, set[str]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self.misses += 1
                return None
            expires, value = item
            if expires < time.monotonic():
                self._data.pop(key, None)
                self.misses += 1
                return None
            self.hits += 1
            return value

    def set(self, key: str, value: Any, ttl: int, account_id: int) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + ttl, value)
            self._index.setdefault(account_id, set()).add(key)

    def invalidate_account(self, account_id: int) -> int:
        with self._lock:
            keys = self._index.pop(account_id, set())
            for k in keys:
                self._data.pop(k, None)
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._index.clear()


class RedisCache:
    backend = "redis"

    def __init__(self, url: str) -> None:
        import redis

        self._r = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)

    def get(self, key: str) -> Any | None:
        raw = self._r.get(key)
        return None if raw is None else json.loads(raw)

    def set(self, key: str, value: Any, ttl: int, account_id: int) -> None:
        pipe = self._r.pipeline()
        pipe.set(key, json.dumps(value, default=str), ex=ttl)
        pipe.sadd(_index_key(account_id), key)
        pipe.expire(_index_key(account_id), max(ttl * 4, 3600))
        pipe.execute()

    def invalidate_account(self, account_id: int) -> int:
        idx = _index_key(account_id)
        keys = list(self._r.smembers(idx))
        pipe = self._r.pipeline()
        if keys:
            pipe.delete(*keys)
        pipe.delete(idx)
        pipe.execute()
        return len(keys)

    def clear(self) -> None:
        for k in self._r.scan_iter("cm:*"):
            self._r.delete(k)


def build_cache(redis_url: str | None) -> Cache:
    if redis_url:
        try:
            cache = RedisCache(redis_url)
            cache._r.ping()
            log.info("cache backend: redis")
            return cache
        except Exception as exc:  # pragma: no cover - depends on env
            log.warning("redis unavailable (%s); falling back to in-memory cache", exc)
    log.info("cache backend: memory")
    return InMemoryCache()
