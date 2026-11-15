"""In-memory per-user token bucket (S20; MVP is a single API instance)."""

from datetime import datetime

from app.core.clock import Clock


class TokenBucket:
    def __init__(self, *, capacity: int, per_seconds: float, clock: Clock) -> None:
        self.capacity = capacity
        self.rate = capacity / per_seconds  # tokens per second
        self.clock = clock
        self._state: dict[str, tuple[float, datetime]] = {}

    def allow(self, key: str) -> bool:
        now = self.clock.now()
        tokens, last = self._state.get(key, (float(self.capacity), now))
        tokens = min(self.capacity, tokens + (now - last).total_seconds() * self.rate)
        if tokens < 1:
            self._state[key] = (tokens, now)
            return False
        self._state[key] = (tokens - 1, now)
        return True
