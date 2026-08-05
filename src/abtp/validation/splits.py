"""Time-series split utilities for walk-forward validation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from abtp.data import normalize_timestamp


@dataclass(frozen=True, slots=True)
class ValidationWindow:
    """One train/test window with explicit index boundaries and timestamps."""

    index: int
    train_start_index: int
    train_end_index: int
    test_start_index: int
    test_end_index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    kind: str
    source_ref: str

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("window index cannot be negative")
        if self.train_start_index < 0:
            raise ValueError("train_start_index cannot be negative")
        if self.train_end_index < self.train_start_index:
            raise ValueError("train window cannot be empty")
        if self.test_start_index <= self.train_end_index:
            raise ValueError("test window must start after train window")
        if self.test_end_index < self.test_start_index:
            raise ValueError("test window cannot be empty")
        if not self.kind.strip():
            raise ValueError("window kind is required")
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        object.__setattr__(self, "train_start", normalize_timestamp(self.train_start))
        object.__setattr__(self, "train_end", normalize_timestamp(self.train_end))
        object.__setattr__(self, "test_start", normalize_timestamp(self.test_start))
        object.__setattr__(self, "test_end", normalize_timestamp(self.test_end))
        if self.train_end >= self.test_start:
            raise ValueError("train_end must be before test_start")

    @property
    def train_size(self) -> int:
        return self.train_end_index - self.train_start_index + 1

    @property
    def test_size(self) -> int:
        return self.test_end_index - self.test_start_index + 1

    def as_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "train_start_index": self.train_start_index,
            "train_end_index": self.train_end_index,
            "test_start_index": self.test_start_index,
            "test_end_index": self.test_end_index,
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
            "train_size": self.train_size,
            "test_size": self.test_size,
            "kind": self.kind,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class TimeSeriesSplitPolicy:
    """Configuration for deterministic time-series validation windows."""

    train_size: int
    test_size: int
    step_size: int | None = None
    gap_size: int = 0
    min_train_size: int | None = None
    source_ref: str = "validation:time_series_split"

    def __post_init__(self) -> None:
        if self.train_size <= 0:
            raise ValueError("train_size must be positive")
        if self.test_size <= 0:
            raise ValueError("test_size must be positive")
        if self.step_size is not None and self.step_size <= 0:
            raise ValueError("step_size must be positive")
        if self.gap_size < 0:
            raise ValueError("gap_size cannot be negative")
        if self.min_train_size is not None and self.min_train_size <= 0:
            raise ValueError("min_train_size must be positive")
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")

    @property
    def active_step_size(self) -> int:
        return self.step_size or self.test_size

    @property
    def active_min_train_size(self) -> int:
        return self.min_train_size or self.train_size


def rolling_window_splits(
    timestamps: Sequence[datetime],
    policy: TimeSeriesSplitPolicy,
) -> tuple[ValidationWindow, ...]:
    """Create fixed-size rolling train/test windows."""

    ordered = _normalize_and_validate_timestamps(timestamps)
    windows: list[ValidationWindow] = []
    start = 0
    index = 0
    while True:
        train_start_index = start
        train_end_index = train_start_index + policy.train_size - 1
        test_start_index = train_end_index + policy.gap_size + 1
        test_end_index = test_start_index + policy.test_size - 1
        if test_end_index >= len(ordered):
            break
        windows.append(
            _build_window(
                ordered,
                index=index,
                train_start_index=train_start_index,
                train_end_index=train_end_index,
                test_start_index=test_start_index,
                test_end_index=test_end_index,
                kind="rolling",
                source_ref=policy.source_ref,
            )
        )
        start += policy.active_step_size
        index += 1
    return tuple(windows)


def expanding_window_splits(
    timestamps: Sequence[datetime],
    policy: TimeSeriesSplitPolicy,
) -> tuple[ValidationWindow, ...]:
    """Create expanding train/test windows that preserve time order."""

    ordered = _normalize_and_validate_timestamps(timestamps)
    windows: list[ValidationWindow] = []
    train_end_index = policy.active_min_train_size - 1
    index = 0
    while True:
        test_start_index = train_end_index + policy.gap_size + 1
        test_end_index = test_start_index + policy.test_size - 1
        if test_end_index >= len(ordered):
            break
        windows.append(
            _build_window(
                ordered,
                index=index,
                train_start_index=0,
                train_end_index=train_end_index,
                test_start_index=test_start_index,
                test_end_index=test_end_index,
                kind="expanding",
                source_ref=policy.source_ref,
            )
        )
        train_end_index += policy.active_step_size
        index += 1
    return tuple(windows)


def time_series_cross_validation_splits(
    timestamps: Sequence[datetime],
    policy: TimeSeriesSplitPolicy,
) -> tuple[ValidationWindow, ...]:
    """Alias for rolling-window validation used by current stages."""

    return rolling_window_splits(timestamps, policy)


def assert_no_leakage(windows: Sequence[ValidationWindow]) -> None:
    """Fail when any test interval overlaps or precedes its training interval."""

    for window in windows:
        if window.train_end >= window.test_start:
            raise ValueError(f"window {window.index} leaks future test data into training")
        if window.train_end_index >= window.test_start_index:
            raise ValueError(f"window {window.index} has overlapping train/test indexes")


def _build_window(
    timestamps: Sequence[datetime],
    *,
    index: int,
    train_start_index: int,
    train_end_index: int,
    test_start_index: int,
    test_end_index: int,
    kind: str,
    source_ref: str,
) -> ValidationWindow:
    return ValidationWindow(
        index=index,
        train_start_index=train_start_index,
        train_end_index=train_end_index,
        test_start_index=test_start_index,
        test_end_index=test_end_index,
        train_start=timestamps[train_start_index],
        train_end=timestamps[train_end_index],
        test_start=timestamps[test_start_index],
        test_end=timestamps[test_end_index],
        kind=kind,
        source_ref=source_ref,
    )


def _normalize_and_validate_timestamps(timestamps: Sequence[datetime]) -> tuple[datetime, ...]:
    ordered = tuple(normalize_timestamp(value) for value in timestamps)
    if len(ordered) < 2:
        raise ValueError("at least two timestamps are required")
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if current <= previous:
            raise ValueError("timestamps must be strictly increasing")
    return ordered
