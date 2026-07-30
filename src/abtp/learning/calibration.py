"""Confidence calibration suggestions for completed trade outcomes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_FLOOR, Decimal

from abtp.data import normalize_timestamp
from abtp.learning.analyzer import (
    DECIMAL_ONE,
    DECIMAL_ZERO,
    MAX_ADVISORY_ADJUSTMENT,
    OutcomeLabel,
    TradeLearningRecord,
)


@dataclass(frozen=True, slots=True)
class ConfidenceBucket:
    """Observed outcome quality for one confidence bucket."""

    lower_bound: Decimal
    upper_bound: Decimal
    sample_count: int
    average_confidence: Decimal
    win_rate: Decimal
    calibration_error: Decimal

    def __post_init__(self) -> None:
        if not DECIMAL_ZERO <= self.lower_bound <= self.upper_bound <= DECIMAL_ONE:
            raise ValueError("confidence bucket bounds must be between 0 and 1")
        if self.sample_count < 0:
            raise ValueError("sample_count cannot be negative")

    @property
    def label(self) -> str:
        return f"{self.lower_bound}-{self.upper_bound}"

    def as_dict(self) -> dict[str, object]:
        return {
            "lower_bound": str(self.lower_bound),
            "upper_bound": str(self.upper_bound),
            "sample_count": self.sample_count,
            "average_confidence": str(self.average_confidence),
            "win_rate": str(self.win_rate),
            "calibration_error": str(self.calibration_error),
        }


@dataclass(frozen=True, slots=True)
class ConfidenceCalibrationSuggestion:
    """Advisory confidence adjustment that must be validated before adoption."""

    target: str
    adjustment: Decimal
    rationale: str
    evidence_refs: tuple[str, ...]
    requires_validation: bool = True
    allowed_to_auto_apply: bool = False

    def __post_init__(self) -> None:
        if not self.target.strip():
            raise ValueError("calibration target is required")
        if not -DECIMAL_ONE <= self.adjustment <= DECIMAL_ONE:
            raise ValueError("adjustment must be between -1 and 1")
        if not self.rationale.strip():
            raise ValueError("rationale is required")
        if not self.requires_validation:
            raise ValueError("confidence suggestions require validation")
        if self.allowed_to_auto_apply:
            raise ValueError("confidence suggestions cannot auto-apply trading changes")

    def as_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "adjustment": str(self.adjustment),
            "rationale": self.rationale,
            "evidence_refs": list(self.evidence_refs),
            "requires_validation": self.requires_validation,
            "allowed_to_auto_apply": self.allowed_to_auto_apply,
        }


@dataclass(frozen=True, slots=True)
class ConfidenceCalibrationReport:
    """Confidence calibration report for completed trades."""

    generated_at: datetime
    buckets: tuple[ConfidenceBucket, ...]
    suggestions: tuple[ConfidenceCalibrationSuggestion, ...]
    limitations: tuple[str, ...] = (
        "Calibration is advisory and must be validated in paper/backtest before adoption.",
        "Calibration does not change Risk Management Engine rules.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "buckets": [bucket.as_dict() for bucket in self.buckets],
            "suggestions": [suggestion.as_dict() for suggestion in self.suggestions],
            "limitations": list(self.limitations),
        }


def calibrate_confidence(
    records: Sequence[TradeLearningRecord],
    *,
    bucket_size: Decimal = Decimal("0.25"),
    minimum_error: Decimal = Decimal("0.05"),
    generated_at: datetime | None = None,
) -> ConfidenceCalibrationReport:
    """Bucket signal confidence against observed win rate."""

    if not DECIMAL_ZERO < bucket_size <= DECIMAL_ONE:
        raise ValueError("bucket_size must be between 0 and 1")
    if minimum_error < DECIMAL_ZERO:
        raise ValueError("minimum_error cannot be negative")
    usable = tuple(record for record in records if record.is_usable_for_learning)
    grouped: dict[Decimal, list[TradeLearningRecord]] = {}
    for record in usable:
        lower = _bucket_lower(record.signal_confidence, bucket_size)
        grouped.setdefault(lower, []).append(record)
    buckets: list[ConfidenceBucket] = []
    suggestions: list[ConfidenceCalibrationSuggestion] = []
    for lower, bucket_records in sorted(grouped.items()):
        upper = min(lower + bucket_size, DECIMAL_ONE)
        average_confidence = _average(tuple(record.signal_confidence for record in bucket_records))
        wins = sum(1 for record in bucket_records if record.outcome is OutcomeLabel.WIN)
        win_rate = Decimal(wins) / Decimal(len(bucket_records))
        error = win_rate - average_confidence
        bucket = ConfidenceBucket(
            lower_bound=lower,
            upper_bound=upper,
            sample_count=len(bucket_records),
            average_confidence=average_confidence,
            win_rate=win_rate,
            calibration_error=error,
        )
        buckets.append(bucket)
        if abs(error) >= minimum_error:
            adjustment = _clamp(
                error / Decimal("2"), -MAX_ADVISORY_ADJUSTMENT, MAX_ADVISORY_ADJUSTMENT
            )
            direction = "increase" if adjustment > DECIMAL_ZERO else "reduce"
            suggestions.append(
                ConfidenceCalibrationSuggestion(
                    target=f"signal_confidence:{bucket.label}",
                    adjustment=adjustment,
                    rationale=(
                        f"{direction} confidence for bucket {bucket.label}; "
                        f"observed win_rate={win_rate} average_confidence={average_confidence}"
                    ),
                    evidence_refs=tuple(record.trade_id for record in bucket_records),
                )
            )
    return ConfidenceCalibrationReport(
        generated_at=generated_at or datetime.now(UTC),
        buckets=tuple(buckets),
        suggestions=tuple(suggestions),
    )


def _bucket_lower(confidence: Decimal, bucket_size: Decimal) -> Decimal:
    if confidence == DECIMAL_ONE:
        return DECIMAL_ONE - bucket_size
    steps = (confidence / bucket_size).to_integral_value(rounding=ROUND_FLOOR)
    return max(DECIMAL_ZERO, min(steps * bucket_size, DECIMAL_ONE - bucket_size))


def _average(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return DECIMAL_ZERO
    return sum(values, DECIMAL_ZERO) / Decimal(len(values))


def _clamp(value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
    return min(max(value, lower), upper)
