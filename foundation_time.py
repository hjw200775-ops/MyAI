"""Validation and rollback-safe clock adapter over V1.6 TimeContextService."""
import math
from threading import RLock
from time_context import default_time_service, parse_timestamp


class FoundationClock:
    def __init__(self, time_service=None):
        self.time_service = time_service or default_time_service
        self._latest = None
        self._lock = RLock()

    def now(self):
        with self._lock:
            now = parse_timestamp(self.time_service.clock())
            if now is None:
                raise ValueError('Invalid clock timestamp')
            if self._latest is None or now >= self._latest:
                self._latest = now
            return self._latest


def timestamp(value):
    parsed = parse_timestamp(value)
    if parsed is None:
        raise ValueError('Invalid timestamp')
    return parsed


def number(value, low, high):
    if isinstance(value, bool):
        raise ValueError('Expected finite number')
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Number out of range')
    return value


foundation_clock = FoundationClock()
