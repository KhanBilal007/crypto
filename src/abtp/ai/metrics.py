"""Deterministic metrics for baseline research predictions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from abtp.ai.datasets import DatasetRow, DirectionLabel


@dataclass(frozen=True, slots=True)
class CalibrationBucket:
    """Simple probability calibration bucket."""

    lower: Decimal
    upper: Decimal
    count: int
    average_probability: Decimal
    observed_rate: Decimal


def accuracy(actual: Sequence[DirectionLabel], predicted: Sequence[DirectionLabel]) -> Decimal:
    _require_same_length(actual, predicted)
    if not actual:
        return Decimal("0")
    correct = sum(1 for left, right in zip(actual, predicted, strict=True) if left is right)
    return Decimal(correct) / Decimal(len(actual))


def directional_hit_rate(
    actual: Sequence[DirectionLabel],
    predicted: Sequence[DirectionLabel],
) -> Decimal:
    directional_pairs = tuple(
        (left, right)
        for left, right in zip(actual, predicted, strict=True)
        if left is not DirectionLabel.FLAT
    )
    if not directional_pairs:
        return Decimal("0")
    correct = sum(1 for left, right in directional_pairs if left is right)
    return Decimal(correct) / Decimal(len(directional_pairs))


def precision_recall(
    actual: Sequence[DirectionLabel],
    predicted: Sequence[DirectionLabel],
    *,
    positive_label: DirectionLabel = DirectionLabel.UP,
) -> tuple[Decimal, Decimal]:
    _require_same_length(actual, predicted)
    true_positive = sum(
        1
        for left, right in zip(actual, predicted, strict=True)
        if left is positive_label and right is positive_label
    )
    predicted_positive = sum(1 for value in predicted if value is positive_label)
    actual_positive = sum(1 for value in actual if value is positive_label)
    precision = _ratio(true_positive, predicted_positive)
    recall = _ratio(true_positive, actual_positive)
    return precision, recall


def mean_absolute_error(actual: Sequence[Decimal], predicted: Sequence[Decimal]) -> Decimal:
    _require_same_length(actual, predicted)
    if not actual:
        return Decimal("0")
    total = sum(
        (abs(left - right) for left, right in zip(actual, predicted, strict=True)),
        Decimal("0"),
    )
    return total / Decimal(len(actual))


def calibration_buckets(
    probabilities: Sequence[Decimal],
    actual_up: Sequence[bool],
    *,
    bucket_size: Decimal = Decimal("0.25"),
) -> tuple[CalibrationBucket, ...]:
    _require_same_length(probabilities, actual_up)
    if bucket_size <= Decimal("0") or bucket_size > Decimal("1"):
        raise ValueError("bucket_size must be in (0, 1]")
    buckets: list[CalibrationBucket] = []
    lower = Decimal("0")
    while lower < Decimal("1"):
        upper = min(Decimal("1"), lower + bucket_size)
        selected = tuple(
            (probability, actual)
            for probability, actual in zip(probabilities, actual_up, strict=True)
            if _in_bucket(probability, lower=lower, upper=upper)
        )
        if selected:
            average_probability = sum((item[0] for item in selected), Decimal("0")) / Decimal(
                len(selected)
            )
            observed_rate = Decimal(sum(1 for _, actual in selected if actual)) / Decimal(
                len(selected)
            )
        else:
            average_probability = Decimal("0")
            observed_rate = Decimal("0")
        buckets.append(
            CalibrationBucket(
                lower=lower,
                upper=upper,
                count=len(selected),
                average_probability=average_probability,
                observed_rate=observed_rate,
            )
        )
        lower = upper
    return tuple(buckets)


def evaluate_directional_predictions(
    rows: Sequence[DatasetRow],
    *,
    predicted_directions: Sequence[DirectionLabel],
    predicted_probabilities_up: Sequence[Decimal],
    predicted_returns: Sequence[Decimal],
    predicted_volatility: Sequence[Decimal],
) -> Mapping[str, Decimal]:
    """Return deterministic metrics for baseline prediction outputs."""

    actual_directions = tuple(row.label.direction for row in rows)
    actual_returns = tuple(row.label.future_return for row in rows)
    actual_volatility = tuple(row.label.future_volatility for row in rows)
    precision, recall = precision_recall(actual_directions, predicted_directions)
    buckets = calibration_buckets(
        predicted_probabilities_up,
        tuple(direction is DirectionLabel.UP for direction in actual_directions),
    )
    calibration_error = mean_absolute_error(
        tuple(bucket.observed_rate for bucket in buckets if bucket.count > 0),
        tuple(bucket.average_probability for bucket in buckets if bucket.count > 0),
    )
    return {
        "accuracy": accuracy(actual_directions, predicted_directions),
        "precision_up": precision,
        "recall_up": recall,
        "directional_hit_rate": directional_hit_rate(actual_directions, predicted_directions),
        "return_mae": mean_absolute_error(actual_returns, predicted_returns),
        "volatility_mae": mean_absolute_error(actual_volatility, predicted_volatility),
        "calibration_error": calibration_error,
    }


def _ratio(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return Decimal("0")
    return Decimal(numerator) / Decimal(denominator)


def _in_bucket(probability: Decimal, *, lower: Decimal, upper: Decimal) -> bool:
    if upper == Decimal("1"):
        return lower <= probability <= upper
    return lower <= probability < upper


def _require_same_length(left: Sequence[object], right: Sequence[object]) -> None:
    if len(left) != len(right):
        raise ValueError("metric inputs must have the same length")
