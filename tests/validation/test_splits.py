from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from abtp.validation import (
    TimeSeriesSplitPolicy,
    assert_no_leakage,
    expanding_window_splits,
    rolling_window_splits,
    time_series_cross_validation_splits,
)

START = datetime(2026, 1, 1, tzinfo=UTC)


def test_rolling_window_splits_preserve_out_of_sample_order() -> None:
    windows = rolling_window_splits(
        _timestamps(10),
        TimeSeriesSplitPolicy(train_size=4, test_size=2, step_size=2),
    )

    assert len(windows) == 3
    assert windows[0].train_start_index == 0
    assert windows[0].train_end_index == 3
    assert windows[0].test_start_index == 4
    assert windows[0].test_end_index == 5
    assert windows[1].train_start_index == 2
    assert windows[1].test_start > windows[1].train_end
    assert_no_leakage(windows)


def test_expanding_window_splits_increase_training_history() -> None:
    windows = expanding_window_splits(
        _timestamps(9),
        TimeSeriesSplitPolicy(train_size=3, test_size=2, step_size=2),
    )

    assert [window.train_size for window in windows] == [3, 5, 7]
    assert [window.kind for window in windows] == ["expanding", "expanding", "expanding"]
    assert_no_leakage(windows)


def test_time_series_cross_validation_is_rolling_alias() -> None:
    policy = TimeSeriesSplitPolicy(train_size=3, test_size=2)

    assert time_series_cross_validation_splits(_timestamps(7), policy) == rolling_window_splits(
        _timestamps(7), policy
    )


def test_unsorted_timestamps_reject_to_prevent_leakage() -> None:
    timestamps = (START, START + timedelta(minutes=2), START + timedelta(minutes=1))

    with pytest.raises(ValueError, match="strictly increasing"):
        rolling_window_splits(timestamps, TimeSeriesSplitPolicy(train_size=2, test_size=1))


def _timestamps(count: int) -> tuple[datetime, ...]:
    return tuple(START + timedelta(minutes=index) for index in range(count))
