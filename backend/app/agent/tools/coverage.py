"""Coverage + freshness block on every tool result (S21 rule 6)."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from app.agent.tools.timefmt import ago

PLATFORMS = ("canvas", "gradescope", "echo360", "piazza")

# Schedule intervals (S10 rule 3); Piazza (S17, stretch) assumed hourly. Stale = older than 2x.
SCHEDULE_INTERVAL = {
    "canvas": timedelta(minutes=20),
    "gradescope": timedelta(minutes=60),
    "echo360": timedelta(days=1),
    "piazza": timedelta(minutes=60),
}


@dataclass
class ConnectionState:
    platform: str
    status: str  # connection_status: active | needs_reconnect | error | disconnected
    last_sync_at: datetime | None


class Coverage(BaseModel):
    searched: list[str] = Field(default_factory=list)
    not_connected: list[str] = Field(default_factory=list)
    needs_reconnect: list[str] = Field(default_factory=list)
    freshness: dict[str, str] = Field(default_factory=dict)
    stale: list[str] = Field(default_factory=list)


def compute_coverage(
    connections: list[ConnectionState], now: datetime, source: str | None = None
) -> Coverage:
    by_platform = {c.platform: c for c in connections if c.status != "disconnected"}
    cov = Coverage()
    for platform in PLATFORMS:
        conn = by_platform.get(platform)
        if conn is None:
            cov.not_connected.append(platform)
            continue
        if source and platform != source:
            continue
        # needs_reconnect / error: older data is still searched, just flagged.
        cov.searched.append(platform)
        if conn.status == "needs_reconnect":
            cov.needs_reconnect.append(platform)
        cov.freshness[platform] = ago(conn.last_sync_at, now)
        if conn.last_sync_at is None or now - conn.last_sync_at > 2 * SCHEDULE_INTERVAL[platform]:
            cov.stale.append(platform)
    return cov
