"""Execution latency observations for reporting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from abtp.data import normalize_timestamp


@dataclass(frozen=True, slots=True)
class ExecutionLatencyRecord:
    """Submit, acknowledgement, and fill timing for one order lifecycle."""

    submitted_at: datetime
    acknowledged_at: datetime | None = None
    completed_at: datetime | None = None
    source_ref: str = "execution:latency"

    def __post_init__(self) -> None:
        submitted_at = normalize_timestamp(self.submitted_at)
        acknowledged_at = (
            normalize_timestamp(self.acknowledged_at) if self.acknowledged_at is not None else None
        )
        completed_at = (
            normalize_timestamp(self.completed_at) if self.completed_at is not None else None
        )
        if acknowledged_at is not None and acknowledged_at < submitted_at:
            raise ValueError("acknowledged_at cannot be before submitted_at")
        if completed_at is not None and completed_at < submitted_at:
            raise ValueError("completed_at cannot be before submitted_at")
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        object.__setattr__(self, "submitted_at", submitted_at)
        object.__setattr__(self, "acknowledged_at", acknowledged_at)
        object.__setattr__(self, "completed_at", completed_at)

    @property
    def acknowledgement_latency(self) -> timedelta | None:
        if self.acknowledged_at is None:
            return None
        return self.acknowledged_at - self.submitted_at

    @property
    def fill_latency(self) -> timedelta | None:
        if self.completed_at is None:
            return None
        return self.completed_at - self.submitted_at

    def as_dict(self) -> dict[str, str | None]:
        return {
            "submitted_at": self.submitted_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat()
            if self.acknowledged_at is not None
            else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at is not None
            else None,
            "acknowledgement_latency_ms": _duration_ms(self.acknowledgement_latency),
            "fill_latency_ms": _duration_ms(self.fill_latency),
            "source_ref": self.source_ref,
        }


def latency_ms(value: timedelta | None) -> int | None:
    """Return a whole-millisecond latency value."""

    if value is None:
        return None
    return int(value.total_seconds() * 1000)


def _duration_ms(value: timedelta | None) -> str | None:
    milliseconds = latency_ms(value)
    return str(milliseconds) if milliseconds is not None else None
