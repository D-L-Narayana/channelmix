"""Report cache with per-workspace invalidation.

Keys are namespaced ``cm:{workspace_id}:{name}:{hash}`` and every key is also recorded in a per-workspace
index so invalidation is an exact O(keys-for-workspace) delete instead of a SCAN over the whole keyspace.

Default backend: in-process **LRU + TTL** (bounded by ``CACHE_MAX_ENTRIES``). Redis is used when
``REDIS_URL`` is configured and reachable (shared cache across instances).
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Protocol

log = logging.getLogger("channelmix.cache")


class Cache(Protocol):
    backend: str

    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl: int, workspace_id: int) -> None: ...
    def invalidate_workspace(self, workspace_id: int) -> int: ...
    def clear(self) -> None: ...


def make_key(workspace_id: int, name: str, params: dict[str, Any]) -> str:
    digest = hashlib.sha1(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return f"cm:{workspace_id}:{name}:{digest}"


def _index_key(workspace_id: int) -> str:
    return f"cm:idx:{workspace_id}"


class InMemoryCache:
    """Thread-safe LRU with per-entry TTL and per-workspace index."""

    backend = "memory"

    def __init__(self, max_entries: int = 2048) -> None:
        self.max_entries = max_entries
        self._data: OrderedDict[str, tuple[float, int, Any]] = OrderedDict()
        self._index: dict[int, set[str]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _drop(self, key: str) -> None:
        item = self._data.pop(key, None)
        if item is not None:
            idx = self._index.get(item[1])
            if idx is not None:
                idx.discard(key)
                if not idx:
                    self._index.pop(item[1], None)

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self.misses += 1
                return None
            expires, _ws, value = item
            if expires < time.monotonic():
                self._drop(key)
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: Any, ttl: int, workspace_id: int) -> None:
        with self._lock:
            if key in self._data:
                self._drop(key)
            self._data[key] = (time.monotonic() + ttl, workspace_id, value)
            self._index.setdefault(workspace_id, set()).add(key)
            while len(self._data) > self.max_entries:
                oldest, _ = next(iter(self._data.items()))
                self._drop(oldest)
                self.evictions += 1

    def invalidate_workspace(self, workspace_id: int) -> int:
        with self._lock:
            keys = self._index.pop(workspace_id, set())
            for k in keys:
                self._data.pop(k, None)
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._index.clear()

    def __len__(self) -> int:
        return len(self._data)


class RedisCache:
    backend = "redis"

    def __init__(self, url: str) -> None:
        import redis

        self._r = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)

    def get(self, key: str) -> Any | None:
        raw = self._r.get(key)
        return None if raw is None else json.loads(raw)

    def set(self, key: str, value: Any, ttl: int, workspace_id: int) -> None:
        pipe = self._r.pipeline()
        pipe.set(key, json.dumps(value, default=str), ex=ttl)
        pipe.sadd(_index_key(workspace_id), key)
        pipe.expire(_index_key(workspace_id), max(ttl * 4, 3600))
        pipe.execute()

    def invalidate_workspace(self, workspace_id: int) -> int:
        idx = _index_key(workspace_id)
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


def build_cache(redis_url: str | None, max_entries: int = 2048) -> Cache:
    if redis_url:
        try:
            cache = RedisCache(redis_url)
            cache._r.ping()
            log.info("cache backend: redis")
            return cache
        except Exception as exc:  # pragma: no cover - depends on env
            log.warning("redis unavailable (%s); falling back to in-memory LRU cache", exc)
    log.info("cache backend: memory (LRU, max %d entries)", max_entries)
    return InMemoryCache(max_entries=max_entries)
