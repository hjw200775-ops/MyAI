"""Optional in-process affect. No model calls, profile writes or emotion.py changes."""
from dataclasses import dataclass
from datetime import timedelta
from threading import RLock
from foundation_time import foundation_clock, number
from time_context import parse_timestamp


@dataclass(frozen=True)
class AffectState:
    valence: float = 0.0
    arousal: float = 0.0
    confidence: float = 0.0
    updated_at: str | None = None
    expires_at: str | None = None


class ShortTermAffect:
    def __init__(self, clock=None):
        self.clock = clock or foundation_clock
        self._state = AffectState()
        self._lock = RLock()

    def set(self, valence, arousal, confidence, ttl_seconds=1800):
        valence = number(valence, -1, 1)
        arousal = number(arousal, 0, 1)
        confidence = number(confidence, 0, 1)
        ttl = number(ttl_seconds, 0.000001, 86400)
        now = self.clock.now()
        state = AffectState(valence, arousal, confidence, now.isoformat(),
                            (now + timedelta(seconds=ttl)).isoformat())
        with self._lock:
            self._state = state
        return state

    def get(self):
        with self._lock:
            state = self._state
            updated, expires = parse_timestamp(state.updated_at), parse_timestamp(state.expires_at)
            now = self.clock.now()
            if updated is None or expires is None or expires <= updated or now >= expires:
                self._state = AffectState()
                return self._state
            # Linear decay to neutral; clock rollback cannot restore old intensity.
            factor = max(0.0, min(1.0, (expires - now).total_seconds() / (expires - updated).total_seconds()))
            return AffectState(state.valence * factor, state.arousal * factor,
                               state.confidence * factor, state.updated_at, state.expires_at)

    def clear(self):
        with self._lock:
            self._state = AffectState()
