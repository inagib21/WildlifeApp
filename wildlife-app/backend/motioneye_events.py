import os
import time
from collections import deque
from typing import Deque, Dict, Tuple

_DEFAULT_TTL = float(os.getenv("MOTIONEYE_EVENT_TTL_SECONDS", "10"))

_recent_events: Deque[Tuple[str, float]] = deque()
_recent_lookup: Dict[str, float] = {}


def _prune(now: float, ttl: float) -> None:
    while _recent_events and now - _recent_events[0][1] > ttl:
        path, _ = _recent_events.popleft()
        stored = _recent_lookup.get(path)
        if stored is None:
            continue
        if now - stored > ttl:
            _recent_lookup.pop(path, None)


def should_process_event(file_path: str, now: float | None = None, ttl: float | None = None) -> bool:
    if not file_path:
        return True
    if now is None:
        now = time.monotonic()
    if ttl is None:
        ttl = _DEFAULT_TTL
    _prune(now, ttl)
    last = _recent_lookup.get(file_path)
    if last is not None and now - last <= ttl:
        return False
    _recent_events.append((file_path, now))
    _recent_lookup[file_path] = now
    return True


def _reset_event_cache() -> None:
    _recent_events.clear()
    _recent_lookup.clear()

