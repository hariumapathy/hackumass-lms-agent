"""Injectable clock (S20): JWKS cache, rate limits and the Today view stay testable."""

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Test clock: returns a fixed time until `advance()` moves it."""

    def __init__(self, at: datetime) -> None:
        self._now = at

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta
