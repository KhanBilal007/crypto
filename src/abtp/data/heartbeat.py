"""Live stream heartbeat and health state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class StreamHealth:
    """Health status emitted by live ingestion."""

    is_connected: bool
    is_stale: bool
    is_degraded: bool
    disconnect_count: int
    last_message_at: datetime | None
    latency_ms: int
    stale_after: timedelta

    @property
    def status(self) -> str:
        if self.is_stale:
            return "stale"
        if self.is_degraded:
            return "degraded"
        if not self.is_connected:
            return "disconnected"
        return "healthy"


class HeartbeatMonitor:
    """Track stream latency, disconnects, stale data, and last message time."""

    def __init__(self, *, stale_after: timedelta, degraded_latency_ms: int) -> None:
        if stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive")
        if degraded_latency_ms < 0:
            raise ValueError("degraded_latency_ms must not be negative")
        self._stale_after = stale_after
        self._degraded_latency_ms = degraded_latency_ms
        self._last_message_at: datetime | None = None
        self._latency_ms = 0
        self._disconnect_count = 0
        self._connected = False

    def mark_connected(self) -> None:
        self._connected = True

    def mark_disconnected(self) -> None:
        self._disconnect_count += 1
        self._connected = False

    def record_message(self, *, provider_timestamp: datetime, received_at: datetime) -> None:
        normalized_provider = _as_utc(provider_timestamp)
        normalized_received = _as_utc(received_at)
        self._last_message_at = normalized_received
        self._latency_ms = max(
            0,
            int((normalized_received - normalized_provider).total_seconds() * 1000),
        )
        self._connected = True

    def health(self, *, now: datetime) -> StreamHealth:
        normalized_now = _as_utc(now)
        is_stale = (
            self._last_message_at is None
            or normalized_now - self._last_message_at > self._stale_after
        )
        is_degraded = self._latency_ms > self._degraded_latency_ms or not self._connected
        return StreamHealth(
            is_connected=self._connected,
            is_stale=is_stale,
            is_degraded=is_degraded,
            disconnect_count=self._disconnect_count,
            last_message_at=self._last_message_at,
            latency_ms=self._latency_ms,
            stale_after=self._stale_after,
        )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
