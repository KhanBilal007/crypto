"""Backfill planning utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from abtp.data.symbols import validate_interval


@dataclass(frozen=True, slots=True)
class BackfillWindow:
    """A deterministic historical candle collection window."""

    start: datetime
    end: datetime
    interval: str
    limit: int


def plan_backfill_windows(
    *,
    start: datetime,
    end: datetime,
    interval: str,
    page_size: int,
) -> tuple[BackfillWindow, ...]:
    """Plan paginated backfill windows for a time range."""

    normalized_interval = validate_interval(interval)
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    normalized_start = _as_utc(start)
    normalized_end = _as_utc(end)
    if normalized_end <= normalized_start:
        raise ValueError("end must be after start")

    step = interval_delta(normalized_interval)
    windows: list[BackfillWindow] = []
    cursor = normalized_start
    while cursor < normalized_end:
        limit = min(page_size, max(1, int((normalized_end - cursor) / step)))
        window_end = min(normalized_end, cursor + (step * limit))
        windows.append(
            BackfillWindow(
                start=cursor,
                end=window_end,
                interval=normalized_interval,
                limit=limit,
            )
        )
        cursor = window_end
    return tuple(windows)


def interval_delta(interval: str) -> timedelta:
    """Return a timedelta for a supported interval."""

    match validate_interval(interval):
        case "1m":
            return timedelta(minutes=1)
        case "5m":
            return timedelta(minutes=5)
        case "15m":
            return timedelta(minutes=15)
        case "1h":
            return timedelta(hours=1)
        case "4h":
            return timedelta(hours=4)
        case "1d":
            return timedelta(days=1)
    raise ValueError(f"unsupported candle interval: {interval}")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
