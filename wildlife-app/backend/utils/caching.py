"""In-memory caching utilities"""
import time
from typing import Optional, Any

# Simple in-memory cache
_cache = {}
_cache_ttl = {}


def get_cached(key: str, ttl: int = 60) -> Optional[Any]:
    """Get cached value if not expired"""
    if key in _cache:
        if time.time() - _cache_ttl.get(key, 0) < ttl:
            return _cache[key]
        else:
            # Cache expired, remove it
            del _cache[key]
            del _cache_ttl[key]
    return None


def set_cached(key: str, value: Any, ttl: int = 60):
    """Set cached value with TTL (time to live in seconds)"""
    _cache[key] = value
    _cache_ttl[key] = time.time()


def clear_cache(key: Optional[str] = None):
    """Clear cache - if key provided, clear only that key, otherwise clear all"""
    if key:
        _cache.pop(key, None)
        _cache_ttl.pop(key, None)
    else:
        _cache.clear()
        _cache_ttl.clear()

