"""Simple in-process TTL cache (no extra dependency)."""

from __future__ import annotations

import time
import threading
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def cache_get(key: str) -> Any | None:
    with _lock:
        item = _store.get(key)
        if not item:
            return None
        expires, value = item
        if time.time() > expires:
            _store.pop(key, None)
            return None
        return value


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    with _lock:
        _store[key] = (time.time() + ttl_seconds, value)


def cache_clear(prefix: str | None = None) -> None:
    with _lock:
        if prefix is None:
            _store.clear()
            return
        for k in list(_store.keys()):
            if k.startswith(prefix):
                _store.pop(k, None)


def cached(key: str, ttl_seconds: int, factory: Callable[[], T]) -> T:
    hit = cache_get(key)
    if hit is not None:
        return hit
    value = factory()
    cache_set(key, value, ttl_seconds)
    return value
