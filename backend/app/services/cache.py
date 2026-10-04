"""Response cache: Redis when configured, in-process TTL map otherwise."""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from app.config import get_settings

_TTL_SECONDS = 60 * 60  # matches SerpApi cache semantics (1h)


class ResponseCache:
    def __init__(self) -> None:
        self._mem: dict[str, tuple[float, str]] = {}
        self._redis = None
        settings = get_settings()
        if settings.redis_url:
            try:
                import redis  # type: ignore

                self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    def get(self, key: str) -> Optional[Any]:
        try:
            if self._redis:
                raw = self._redis.get(key)
                return json.loads(raw) if raw else None
            expiry, raw = self._mem.get(key, (0, ""))
            if raw and expiry > time.time():
                return json.loads(raw)
            self._mem.pop(key, None)
        except Exception:
            return None
        return None

    def set(self, key: str, value: Any, ttl: int = _TTL_SECONDS) -> None:
        try:
            raw = json.dumps(value, default=str)
            if self._redis:
                self._redis.setex(key, ttl, raw)
            else:
                self._mem[key] = (time.time() + ttl, raw)
        except Exception:
            pass


_cache: Optional[ResponseCache] = None


def get_cache() -> ResponseCache:
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache
