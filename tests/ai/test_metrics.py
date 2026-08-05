from __future__ import annotations

from decimal import Decimal

import pytest

from abtp.ai import (
    DirectionLabel,
    accuracy,
    calibration_buckets,
    directional_hit_rate,
    mean_absolute_error,
    precision_recall,
)


def test_classification_metrics_are_deterministic() -> None:
    actual = (DirectionLabel.UP, DirectionLabel.DOWN, DirectionLabel.UP, DirectionLabel.FLAT)
    predicted = (DirectionLabel.UP, DirectionLabel.UP, DirectionLabel.UP, DirectionLabel.FLAT)

    precision, recall = precision_recall(actual, predicted)

    assert accuracy(actual, predicted) == Decimal("0.75")
    assert directional_hit_rate(actual, predicted) == Decimal("0.6666666666666666666666666667")
    assert precision == Decimal("0.6666666666666666666666666667")
    assert recall == Decimal("1")


def test_regression_and_calibration_metrics() -> None:
    assert mean_absolute_error(
        (Decimal("0.10"), Decimal("-0.05")),
        (Decimal("0.00"), Decimal("-0.02")),
    ) == Decimal("0.065")

    buckets = calibration_buckets(
        (Decimal("0.10"), Decimal("0.60"), Decimal("0.90")),
        (False, True, True),
        bucket_size=Decimal("0.50"),
    )

    assert len(buckets) == 2
    assert buckets[0].count == 1
    assert buckets[0].observed_rate == Decimal("0")
    assert buckets[1].count == 2
    assert buckets[1].observed_rate == Decimal("1")


def test_metrics_reject_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        accuracy((DirectionLabel.UP,), ())
