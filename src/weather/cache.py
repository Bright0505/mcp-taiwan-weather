"""TTL cache for CWA API responses."""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TtlCache:
    """Simple in-memory cache with TTL expiration."""

    def __init__(self, ttl_hours: int = 24):
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl_seconds = ttl_hours * 3600

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        data, expiry = entry
        if time.time() > expiry:
            del self._store[key]
            logger.info(f"Cache expired: {key}")
            return None
        logger.info(f"Cache hit: {key}")
        return data

    def set(self, key: str, data: Any) -> None:
        self._store[key] = (data, time.time() + self._ttl_seconds)
        logger.info(f"Cache set: {key} (TTL: {self._ttl_seconds}s)")

    def clear(self) -> None:
        self._store.clear()
        logger.info("Cache cleared")
