"""Read-only continuous performance analytics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from abtp.backtesting.metrics import calculate_max_drawdown
from abtp.data.normalization import normalize_timestamp
from abtp.data.quality import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


class PerformanceWindowKind(StrEnum):
    """Standard continuous analytics windows."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    LONG_TERM = "long_term"


@dataclass(frozen=True, slots=True)
class PerformanceObservation:
    """Stored or fixture evidence for one performance analytics point."""

    observed_at: datetime
    strategy_name: str
    regime_label: str
    equity: Decimal
    realized_pnl: Decimal
    fees_paid: Decimal
    slippage_bps: Decimal
    trade_count: int = 0
    risk_breach_count: int = 0
    prediction_correct: bool | None = None
    execution_quality_score: Decimal | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy_name.strip():
            raise ValueError("strategy_name is required")
        if not self.regime_label.strip():
            raise ValueError("regime_label is required")
        if self.equity <= DECIMAL_ZERO:
            raise ValueError("equity must be positive")
        if self.fees_paid < DECIMAL_ZERO:
            raise ValueError("fees_paid cannot be negative")
        if self.slippage_bps < DECIMAL_ZERO:
            raise ValueError("slippage_bps cannot be negative")
        if self.trade_count < 0:
            raise ValueError("trade_count cannot be negative")
        if self.risk_breach_count < 0:
            raise ValueError("risk_breach_count cannot be negative")
        if self.execution_quality_score is not None and not (
            DECIMAL_ZERO <= self.execution_quality_score <= DECIMAL_ONE
        ):
            raise ValueError("execution_quality_score must be between 0 and 1")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "strategy_name", self.strategy_name.strip())
        object.__setattr__(self, "regime_label", self.regime_label.strip())
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class PerformanceWindow:
    """A deterministic analytics window."""

    kind: PerformanceWindowKind
    start_at: datetime
    end_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", PerformanceWindowKind(self.kind))
        object.__setattr__(self, "start_at", normalize_timestamp(self.start_at))
        object.__setattr__(self, "end_at", normalize_timestamp(self.end_at))
        if self.end_at <= self.start_at:
            raise ValueError("performance window end_at must be after start_at")

    def contains(self, observed_at: datetime) -> bool:
        normalized = normalize_timestamp(observed_at)
        return self.start_at <= normalized < self.end_at

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind.value,
            "start_at": self.start_at.isoformat(),
            "end_at": self.end_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PerformanceWindowReport:
    """Read-only performance report for one analytics window."""

    generated_at: datetime
    window: PerformanceWindow
    starting_equity: Decimal
    ending_equity: Decimal
    net_pnl: Decimal
    net_return: Decimal
    max_drawdown: Decimal
    total_fees: Decimal
    average_slippage_bps: Decimal
    trade_count: int
    risk_breach_count: int
    prediction_accuracy: Decimal | None
    average_execution_quality: Decimal | None
    strategy_count: int
    regime_count: int
    observation_count: int
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Performance analytics are read-only and advisory.",
        "Reports cannot modify strategies, approve risk, create order intents, or execute orders.",
        "Costs, fees, slippage, drawdown, and risk breaches must be reviewed together.",
        "Historical or paper performance does not guarantee profit.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if self.starting_equity <= DECIMAL_ZERO or self.ending_equity <= DECIMAL_ZERO:
            raise ValueError("equity values must be positive")
        if self.max_drawdown < DECIMAL_ZERO:
            raise ValueError("max_drawdown cannot be negative")
        if self.total_fees < DECIMAL_ZERO or self.average_slippage_bps < DECIMAL_ZERO:
            raise ValueError("cost metrics cannot be negative")
        if self.trade_count < 0 or self.risk_breach_count < 0 or self.observation_count < 0:
            raise ValueError("counts cannot be negative")
        if self.strategy_count < 0 or self.regime_count < 0:
            raise ValueError("counts cannot be negative")
        if self.prediction_accuracy is not None and not (
            DECIMAL_ZERO <= self.prediction_accuracy <= DECIMAL_ONE
        ):
            raise ValueError("prediction_accuracy must be between 0 and 1")
        if self.average_execution_quality is not None and not (
            DECIMAL_ZERO <= self.average_execution_quality <= DECIMAL_ONE
        ):
            raise ValueError("average_execution_quality must be between 0 and 1")
        if not self.limitations:
            raise ValueError("performance report limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "window": self.window.as_dict(),
            "starting_equity": str(self.starting_equity),
            "ending_equity": str(self.ending_equity),
            "net_pnl": str(self.net_pnl),
            "net_return": str(self.net_return),
            "max_drawdown": str(self.max_drawdown),
            "total_fees": str(self.total_fees),
            "average_slippage_bps": str(self.average_slippage_bps),
            "trade_count": self.trade_count,
            "risk_breach_count": self.risk_breach_count,
            "prediction_accuracy": None
            if self.prediction_accuracy is None
            else str(self.prediction_accuracy),
            "average_execution_quality": None
            if self.average_execution_quality is None
            else str(self.average_execution_quality),
            "strategy_count": self.strategy_count,
            "regime_count": self.regime_count,
            "observation_count": self.observation_count,
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "window": self.window.kind.value,
            "start_at": self.window.start_at.isoformat(),
            "end_at": self.window.end_at.isoformat(),
            "net_return": str(self.net_return),
            "max_drawdown": str(self.max_drawdown),
            "total_fees": str(self.total_fees),
            "average_slippage_bps": str(self.average_slippage_bps),
            "risk_breach_count": str(self.risk_breach_count),
            "trade_count": str(self.trade_count),
            "quality": self.quality.trust_level.value,
            "quality_flags": "|".join(self.quality.flags),
        }

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        """Reject order-intent authority."""

        raise ValueError("performance analytics cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        """Reject risk-approval authority."""

        raise ValueError("performance analytics cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject execution authority."""

        raise ValueError("performance analytics cannot submit orders")

    def apply_strategy_change(self, *_args: object, **_kwargs: object) -> None:
        """Reject automatic strategy changes."""

        raise ValueError("performance analytics cannot apply strategy changes")


def build_performance_window_report(
    observations: Sequence[PerformanceObservation],
    *,
    window: PerformanceWindow,
    generated_at: datetime,
) -> PerformanceWindowReport:
    """Build one deterministic performance report from supplied observations."""

    selected = tuple(
        sorted(
            (item for item in observations if window.contains(item.observed_at)),
            key=lambda item: item.observed_at,
        )
    )
    if not selected:
        quality = DataQualityStatus(
            trust_level=DataTrustLevel.REJECTED,
            issues=(
                DataQualityIssue(
                    flag="analytics_missing_observations",
                    severity=DataTrustLevel.REJECTED,
                    reason=f"no observations for {window.kind.value} analytics window",
                ),
            ),
            source_ref=f"analytics:{window.kind.value}",
            checked_at=generated_at,
        )
        return PerformanceWindowReport(
            generated_at=generated_at,
            window=window,
            starting_equity=DECIMAL_ONE,
            ending_equity=DECIMAL_ONE,
            net_pnl=DECIMAL_ZERO,
            net_return=DECIMAL_ZERO,
            max_drawdown=DECIMAL_ZERO,
            total_fees=DECIMAL_ZERO,
            average_slippage_bps=DECIMAL_ZERO,
            trade_count=0,
            risk_breach_count=0,
            prediction_accuracy=None,
            average_execution_quality=None,
            strategy_count=0,
            regime_count=0,
            observation_count=0,
            quality=quality,
            source_refs={"window": f"{window.start_at.isoformat()}:{window.end_at.isoformat()}"},
        )

    starting_equity = selected[0].equity
    ending_equity = selected[-1].equity
    prediction_values = tuple(
        item.prediction_correct for item in selected if item.prediction_correct is not None
    )
    execution_values = tuple(
        item.execution_quality_score
        for item in selected
        if item.execution_quality_score is not None
    )
    risk_breach_count = sum(item.risk_breach_count for item in selected)
    quality = _report_quality(
        selected, generated_at=generated_at, risk_breach_count=risk_breach_count
    )
    return PerformanceWindowReport(
        generated_at=generated_at,
        window=window,
        starting_equity=starting_equity,
        ending_equity=ending_equity,
        net_pnl=sum((item.realized_pnl for item in selected), DECIMAL_ZERO),
        net_return=_net_return(starting_equity, ending_equity),
        max_drawdown=calculate_max_drawdown(tuple(item.equity for item in selected)),
        total_fees=sum((item.fees_paid for item in selected), DECIMAL_ZERO),
        average_slippage_bps=_mean(tuple(item.slippage_bps for item in selected)),
        trade_count=sum(item.trade_count for item in selected),
        risk_breach_count=risk_breach_count,
        prediction_accuracy=_prediction_accuracy(prediction_values),
        average_execution_quality=(_mean(execution_values) if execution_values else None),
        strategy_count=len({item.strategy_name for item in selected}),
        regime_count=len({item.regime_label for item in selected}),
        observation_count=len(selected),
        quality=quality,
        source_refs=_source_refs(
            selected, {"window": f"{window.start_at.isoformat()}:{window.end_at.isoformat()}"}
        ),
    )


def build_standard_performance_reports(
    observations: Sequence[PerformanceObservation],
    *,
    generated_at: datetime,
) -> tuple[PerformanceWindowReport, ...]:
    """Build daily, weekly, monthly, and long-term reports for an operator view."""

    checked_at = normalize_timestamp(generated_at)
    windows = (
        daily_window(checked_at),
        weekly_window(checked_at),
        monthly_window(checked_at),
        long_term_window(observations, generated_at=checked_at),
    )
    return tuple(
        build_performance_window_report(
            observations,
            window=window,
            generated_at=checked_at,
        )
        for window in windows
    )


def daily_window(as_of: datetime) -> PerformanceWindow:
    checked_at = normalize_timestamp(as_of)
    start = checked_at.replace(hour=0, minute=0, second=0, microsecond=0)
    return PerformanceWindow(
        kind=PerformanceWindowKind.DAILY,
        start_at=start,
        end_at=start + timedelta(days=1),
    )


def weekly_window(as_of: datetime) -> PerformanceWindow:
    checked_at = normalize_timestamp(as_of)
    day_start = checked_at.replace(hour=0, minute=0, second=0, microsecond=0)
    start = day_start - timedelta(days=day_start.weekday())
    return PerformanceWindow(
        kind=PerformanceWindowKind.WEEKLY,
        start_at=start,
        end_at=start + timedelta(days=7),
    )


def monthly_window(as_of: datetime) -> PerformanceWindow:
    checked_at = normalize_timestamp(as_of)
    start = checked_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return PerformanceWindow(
        kind=PerformanceWindowKind.MONTHLY,
        start_at=start,
        end_at=end,
    )


def long_term_window(
    observations: Sequence[PerformanceObservation],
    *,
    generated_at: datetime,
) -> PerformanceWindow:
    checked_at = normalize_timestamp(generated_at)
    if not observations:
        start = checked_at - timedelta(days=1)
    else:
        earliest = min(observations, key=lambda item: item.observed_at).observed_at
        start = earliest.replace(hour=0, minute=0, second=0, microsecond=0)
    return PerformanceWindow(
        kind=PerformanceWindowKind.LONG_TERM,
        start_at=start,
        end_at=checked_at + timedelta(microseconds=1),
    )


def _net_return(starting_equity: Decimal, ending_equity: Decimal) -> Decimal:
    if starting_equity <= DECIMAL_ZERO:
        return DECIMAL_ZERO
    return ((ending_equity / starting_equity) - DECIMAL_ONE).quantize(SCORE_QUANT)


def _mean(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        return DECIMAL_ZERO
    return (sum(values, DECIMAL_ZERO) / Decimal(len(values))).quantize(SCORE_QUANT)


def _prediction_accuracy(values: tuple[bool, ...]) -> Decimal | None:
    if not values:
        return None
    correct = sum(1 for value in values if value)
    return (Decimal(correct) / Decimal(len(values))).quantize(SCORE_QUANT)


def _report_quality(
    selected: tuple[PerformanceObservation, ...],
    *,
    generated_at: datetime,
    risk_breach_count: int,
) -> DataQualityStatus:
    issues: list[DataQualityIssue] = []
    if risk_breach_count:
        issues.append(
            DataQualityIssue(
                flag="analytics_risk_breaches_present",
                severity=DataTrustLevel.DEGRADED,
                reason="performance window includes risk breaches",
            )
        )
    if any(item.trade_count and item.fees_paid == DECIMAL_ZERO for item in selected):
        issues.append(
            DataQualityIssue(
                flag="analytics_missing_fee_costs",
                severity=DataTrustLevel.DEGRADED,
                reason="one or more traded observations have zero recorded fees",
            )
        )
    trust = DataTrustLevel.DEGRADED if issues else DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=tuple(issues),
        source_ref="analytics:performance",
        checked_at=generated_at,
    )


def _source_refs(
    observations: tuple[PerformanceObservation, ...],
    initial: Mapping[str, str] | None = None,
) -> Mapping[str, str]:
    refs = dict(initial or {})
    for index, item in enumerate(observations):
        refs.setdefault(f"observation_{index}", item.observed_at.isoformat())
        refs.update(item.source_refs)
    return refs


def now_utc() -> datetime:
    """Return current UTC time for callers that need a default timestamp."""

    return datetime.now(UTC)
