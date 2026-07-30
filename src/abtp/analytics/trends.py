"""Read-only trend and comparison analytics."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.analytics.performance import (
    DECIMAL_ONE,
    DECIMAL_ZERO,
    SCORE_QUANT,
    PerformanceObservation,
)
from abtp.backtesting.metrics import calculate_max_drawdown, calculate_win_rate
from abtp.data.normalization import normalize_timestamp
from abtp.data.quality import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain.models import JsonValue


class TrendMetric(StrEnum):
    """Continuous analytics trend dimensions."""

    AI_ACCURACY = "ai_accuracy"
    RISK_BREACHES = "risk_breaches"
    DRAWDOWN = "drawdown"
    EXECUTION_QUALITY = "execution_quality"


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    """Strategy or regime comparison row."""

    label: str
    observation_count: int
    trade_count: int
    net_pnl: Decimal
    net_return: Decimal
    win_rate: Decimal
    max_drawdown: Decimal
    risk_breach_count: int
    average_execution_quality: Decimal | None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("comparison label is required")
        if self.observation_count < 0 or self.trade_count < 0 or self.risk_breach_count < 0:
            raise ValueError("comparison counts cannot be negative")
        if self.max_drawdown < DECIMAL_ZERO:
            raise ValueError("max_drawdown cannot be negative")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "observation_count": self.observation_count,
            "trade_count": self.trade_count,
            "net_pnl": str(self.net_pnl),
            "net_return": str(self.net_return),
            "win_rate": str(self.win_rate),
            "max_drawdown": str(self.max_drawdown),
            "risk_breach_count": self.risk_breach_count,
            "average_execution_quality": None
            if self.average_execution_quality is None
            else str(self.average_execution_quality),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class TrendPoint:
    """One deterministic trend point."""

    period: str
    value: Decimal
    sample_count: int
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.period.strip():
            raise ValueError("trend period is required")
        if self.sample_count < 0:
            raise ValueError("sample_count cannot be negative")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "period": self.period,
            "value": str(self.value),
            "sample_count": self.sample_count,
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class TrendReport:
    """Read-only trend report for one metric."""

    metric: TrendMetric
    generated_at: datetime
    points: tuple[TrendPoint, ...]
    summary: str
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Trend analytics are read-only and advisory.",
        "Trend reports cannot create orders, approve risk, or change strategies.",
        "No profit is guaranteed by trend analytics.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric", TrendMetric(self.metric))
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if not self.summary.strip():
            raise ValueError("trend summary is required")
        if not self.limitations:
            raise ValueError("trend limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "metric": self.metric.value,
            "generated_at": self.generated_at.isoformat(),
            "points": [point.as_dict() for point in self.points],
            "summary": self.summary,
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "metric": self.metric.value,
            "point_count": str(len(self.points)),
            "summary": self.summary,
            "quality": self.quality.trust_level.value,
            "quality_flags": "|".join(self.quality.flags),
        }

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("trend analytics cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("trend analytics cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("trend analytics cannot submit orders")

    def apply_strategy_change(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("trend analytics cannot apply strategy changes")


def compare_strategies(observations: Sequence[PerformanceObservation]) -> tuple[ComparisonRow, ...]:
    """Return deterministic strategy comparison rows."""

    return _compare_by(observations, key_name="strategy")


def compare_regimes(observations: Sequence[PerformanceObservation]) -> tuple[ComparisonRow, ...]:
    """Return deterministic regime comparison rows."""

    return _compare_by(observations, key_name="regime")


def build_ai_accuracy_trend(
    observations: Sequence[PerformanceObservation],
    *,
    generated_at: datetime,
) -> TrendReport:
    """Build daily AI prediction accuracy trend points."""

    return _trend_report(
        observations,
        metric=TrendMetric.AI_ACCURACY,
        generated_at=generated_at,
        value_fn=_prediction_accuracy,
        summary_label="AI prediction accuracy",
    )


def build_risk_trend(
    observations: Sequence[PerformanceObservation],
    *,
    generated_at: datetime,
) -> TrendReport:
    """Build daily risk-breach trend points."""

    return _trend_report(
        observations,
        metric=TrendMetric.RISK_BREACHES,
        generated_at=generated_at,
        value_fn=lambda items: Decimal(sum(item.risk_breach_count for item in items)),
        summary_label="Risk breach count",
    )


def build_drawdown_trend(
    observations: Sequence[PerformanceObservation],
    *,
    generated_at: datetime,
) -> TrendReport:
    """Build daily drawdown trend points."""

    return _trend_report(
        observations,
        metric=TrendMetric.DRAWDOWN,
        generated_at=generated_at,
        value_fn=lambda items: calculate_max_drawdown(tuple(item.equity for item in items)),
        summary_label="Maximum drawdown",
    )


def build_execution_trend(
    observations: Sequence[PerformanceObservation],
    *,
    generated_at: datetime,
) -> TrendReport:
    """Build daily execution-quality trend points."""

    return _trend_report(
        observations,
        metric=TrendMetric.EXECUTION_QUALITY,
        generated_at=generated_at,
        value_fn=_execution_quality,
        summary_label="Execution quality",
    )


def _compare_by(
    observations: Sequence[PerformanceObservation],
    *,
    key_name: str,
) -> tuple[ComparisonRow, ...]:
    grouped: dict[str, list[PerformanceObservation]] = {}
    for item in observations:
        label = item.strategy_name if key_name == "strategy" else item.regime_label
        grouped.setdefault(label, []).append(item)
    rows = tuple(_comparison_row(label, tuple(items)) for label, items in grouped.items())
    return tuple(sorted(rows, key=lambda row: (-row.net_return, row.label)))


def _comparison_row(label: str, observations: tuple[PerformanceObservation, ...]) -> ComparisonRow:
    ordered = tuple(sorted(observations, key=lambda item: item.observed_at))
    starting_equity = ordered[0].equity
    ending_equity = ordered[-1].equity
    execution_values = tuple(
        item.execution_quality_score for item in ordered if item.execution_quality_score is not None
    )
    return ComparisonRow(
        label=label,
        observation_count=len(ordered),
        trade_count=sum(item.trade_count for item in ordered),
        net_pnl=sum((item.realized_pnl for item in ordered), DECIMAL_ZERO),
        net_return=_net_return(starting_equity, ending_equity),
        win_rate=calculate_win_rate(tuple(item.realized_pnl for item in ordered)),
        max_drawdown=calculate_max_drawdown(tuple(item.equity for item in ordered)),
        risk_breach_count=sum(item.risk_breach_count for item in ordered),
        average_execution_quality=_mean(execution_values) if execution_values else None,
        source_refs=_source_refs(ordered),
    )


def _trend_report(
    observations: Sequence[PerformanceObservation],
    *,
    metric: TrendMetric,
    generated_at: datetime,
    value_fn: Callable[[tuple[PerformanceObservation, ...]], Decimal],
    summary_label: str,
) -> TrendReport:
    grouped = _group_by_day(observations)
    points = tuple(
        TrendPoint(
            period=period,
            value=value_fn(tuple(items)).quantize(SCORE_QUANT),
            sample_count=len(items),
            source_refs=_source_refs(tuple(items)),
        )
        for period, items in sorted(grouped.items())
    )
    quality = _trend_quality(points, metric=metric, generated_at=generated_at)
    latest = points[-1].value if points else DECIMAL_ZERO
    return TrendReport(
        metric=metric,
        generated_at=generated_at,
        points=points,
        summary=f"{summary_label} latest={latest} across {len(points)} periods",
        quality=quality,
        source_refs={"metric": metric.value},
    )


def _group_by_day(
    observations: Sequence[PerformanceObservation],
) -> Mapping[str, tuple[PerformanceObservation, ...]]:
    grouped: dict[str, list[PerformanceObservation]] = {}
    for item in observations:
        grouped.setdefault(item.observed_at.date().isoformat(), []).append(item)
    return {key: tuple(values) for key, values in grouped.items()}


def _prediction_accuracy(items: tuple[PerformanceObservation, ...]) -> Decimal:
    values = tuple(item.prediction_correct for item in items if item.prediction_correct is not None)
    if not values:
        return DECIMAL_ZERO
    return Decimal(sum(1 for value in values if value)) / Decimal(len(values))


def _execution_quality(items: tuple[PerformanceObservation, ...]) -> Decimal:
    values = tuple(
        item.execution_quality_score for item in items if item.execution_quality_score is not None
    )
    return _mean(values) if values else DECIMAL_ZERO


def _trend_quality(
    points: tuple[TrendPoint, ...],
    *,
    metric: TrendMetric,
    generated_at: datetime,
) -> DataQualityStatus:
    if not points:
        return DataQualityStatus(
            trust_level=DataTrustLevel.REJECTED,
            issues=(
                DataQualityIssue(
                    flag=f"analytics_{metric.value}_missing_points",
                    severity=DataTrustLevel.REJECTED,
                    reason=f"no points for {metric.value} trend",
                ),
            ),
            source_ref=f"analytics:{metric.value}",
            checked_at=generated_at,
        )
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref=f"analytics:{metric.value}",
        checked_at=generated_at,
    )


def _net_return(starting_equity: Decimal, ending_equity: Decimal) -> Decimal:
    if starting_equity <= DECIMAL_ZERO:
        return DECIMAL_ZERO
    return ((ending_equity / starting_equity) - DECIMAL_ONE).quantize(SCORE_QUANT)


def _mean(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        return DECIMAL_ZERO
    return (sum(values, DECIMAL_ZERO) / Decimal(len(values))).quantize(SCORE_QUANT)


def _source_refs(observations: tuple[PerformanceObservation, ...]) -> Mapping[str, str]:
    refs: dict[str, str] = {}
    for index, item in enumerate(observations):
        refs.setdefault(f"observation_{index}", item.observed_at.isoformat())
        refs.update(item.source_refs)
    return refs
