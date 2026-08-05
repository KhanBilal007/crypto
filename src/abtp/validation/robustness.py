"""Strategy robustness scoring for walk-forward validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from abtp.backtesting import PerformanceMetrics, RegimePerformance
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.validation.splits import ValidationWindow

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class WindowMetricResult:
    """In-sample and out-of-sample metrics for one validation window."""

    strategy_name: str
    window: ValidationWindow
    in_sample_metrics: PerformanceMetrics
    out_of_sample_metrics: PerformanceMetrics
    parameters: Mapping[str, Decimal | str | int] = field(default_factory=dict)
    quality: DataQualityStatus | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy_name.strip():
            raise ValueError("strategy_name is required")
        object.__setattr__(self, "parameters", dict(self.parameters))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def active_quality(self) -> DataQualityStatus:
        if self.quality is not None:
            return self.quality
        return DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref=f"walk_forward:{self.strategy_name}:window:{self.window.index}",
            checked_at=self.window.test_end,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "strategy_name": self.strategy_name,
            "window": self.window.as_dict(),
            "in_sample_metrics": self.in_sample_metrics.as_dict(),
            "out_of_sample_metrics": self.out_of_sample_metrics.as_dict(),
            "parameters": {key: str(value) for key, value in self.parameters.items()},
            "quality": self.active_quality.trust_level.value,
            "quality_flags": list(self.active_quality.flags),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class RobustnessPolicy:
    """Conservative promotion thresholds for walk-forward validation."""

    min_windows: int = 3
    min_pass_ratio: Decimal = Decimal("0.67")
    min_average_oos_return: Decimal = Decimal("0")
    max_oos_drawdown: Decimal = Decimal("0.15")
    max_tail_loss: Decimal = Decimal("0.06")
    min_profit_factor: Decimal = Decimal("1")
    max_train_test_return_gap: Decimal = Decimal("0.12")
    min_parameter_stability: Decimal = Decimal("0.60")
    min_regime_periods: int = 2
    require_costs_included: bool = True
    policy_version: str = "stage-039.v1"

    def __post_init__(self) -> None:
        if self.min_windows <= 0:
            raise ValueError("min_windows must be positive")
        if not DECIMAL_ZERO <= self.min_pass_ratio <= DECIMAL_ONE:
            raise ValueError("min_pass_ratio must be between 0 and 1")
        if not DECIMAL_ZERO <= self.max_oos_drawdown <= DECIMAL_ONE:
            raise ValueError("max_oos_drawdown must be between 0 and 1")
        if not DECIMAL_ZERO <= self.max_tail_loss <= DECIMAL_ONE:
            raise ValueError("max_tail_loss must be between 0 and 1")
        if self.min_profit_factor < DECIMAL_ZERO:
            raise ValueError("min_profit_factor cannot be negative")
        if self.max_train_test_return_gap < DECIMAL_ZERO:
            raise ValueError("max_train_test_return_gap cannot be negative")
        if not DECIMAL_ZERO <= self.min_parameter_stability <= DECIMAL_ONE:
            raise ValueError("min_parameter_stability must be between 0 and 1")
        if self.min_regime_periods < 0:
            raise ValueError("min_regime_periods cannot be negative")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class RobustnessScore:
    """Aggregated robustness evidence for strategy promotion decisions."""

    strategy_name: str
    total_score: Decimal
    pass_ratio: Decimal
    average_out_of_sample_return: Decimal
    worst_out_of_sample_drawdown: Decimal
    average_train_test_return_gap: Decimal
    parameter_stability_score: Decimal
    regime_coverage: Mapping[str, int]
    accepted_for_promotion: bool
    rejected_reasons: tuple[str, ...]
    evidence: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if not self.strategy_name.strip():
            raise ValueError("strategy_name is required")
        for field_name, value in (
            ("total_score", self.total_score),
            ("pass_ratio", self.pass_ratio),
            ("parameter_stability_score", self.parameter_stability_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{field_name} must be between 0 and 1")
        if not self.evidence:
            raise ValueError("robustness score requires evidence")
        object.__setattr__(self, "regime_coverage", dict(self.regime_coverage))
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))

    def as_dict(self) -> dict[str, object]:
        return {
            "strategy_name": self.strategy_name,
            "total_score": str(self.total_score),
            "pass_ratio": str(self.pass_ratio),
            "average_out_of_sample_return": str(self.average_out_of_sample_return),
            "worst_out_of_sample_drawdown": str(self.worst_out_of_sample_drawdown),
            "average_train_test_return_gap": str(self.average_train_test_return_gap),
            "parameter_stability_score": str(self.parameter_stability_score),
            "regime_coverage": dict(self.regime_coverage),
            "accepted_for_promotion": self.accepted_for_promotion,
            "rejected_reasons": list(self.rejected_reasons),
            "evidence": list(self.evidence),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "generated_at": self.generated_at.isoformat(),
        }


def score_robustness(
    results: Sequence[WindowMetricResult],
    *,
    policy: RobustnessPolicy | None = None,
    required_regime: str | None = None,
    generated_at: datetime | None = None,
) -> RobustnessScore:
    """Score walk-forward results and reject fragile or overfitted strategies."""

    active_policy = policy or RobustnessPolicy()
    if not results:
        raise ValueError("at least one window result is required")
    strategy_name = _single_strategy_name(results)
    pass_ratio = _pass_ratio(results, active_policy)
    average_oos_return = _average(tuple(item.out_of_sample_metrics.net_return for item in results))
    worst_oos_drawdown = max(item.out_of_sample_metrics.max_drawdown for item in results)
    average_gap = _average_train_test_gap(results)
    parameter_stability = _parameter_stability(results)
    regime_coverage = _regime_coverage(results)
    reasons = _rejection_reasons(
        results,
        pass_ratio=pass_ratio,
        average_oos_return=average_oos_return,
        worst_oos_drawdown=worst_oos_drawdown,
        average_gap=average_gap,
        parameter_stability=parameter_stability,
        regime_coverage=regime_coverage,
        required_regime=required_regime,
        policy=active_policy,
    )
    quality = _quality(results, reasons, generated_at or datetime.now(UTC), strategy_name)
    accepted = not reasons and quality.is_trusted
    score = _total_score(
        pass_ratio=pass_ratio,
        average_oos_return=average_oos_return,
        worst_oos_drawdown=worst_oos_drawdown,
        average_gap=average_gap,
        parameter_stability=parameter_stability,
        policy=active_policy,
    )
    return RobustnessScore(
        strategy_name=strategy_name,
        total_score=score,
        pass_ratio=pass_ratio,
        average_out_of_sample_return=average_oos_return,
        worst_out_of_sample_drawdown=worst_oos_drawdown,
        average_train_test_return_gap=average_gap,
        parameter_stability_score=parameter_stability,
        regime_coverage=regime_coverage,
        accepted_for_promotion=accepted,
        rejected_reasons=tuple(dict.fromkeys(reasons)),
        evidence=_evidence(
            results,
            pass_ratio=pass_ratio,
            average_oos_return=average_oos_return,
            worst_oos_drawdown=worst_oos_drawdown,
            average_gap=average_gap,
            parameter_stability=parameter_stability,
            required_regime=required_regime,
        ),
        quality=quality,
        policy_version=active_policy.policy_version,
        generated_at=generated_at or datetime.now(UTC),
    )


def _single_strategy_name(results: Sequence[WindowMetricResult]) -> str:
    names = {item.strategy_name for item in results}
    if len(names) != 1:
        raise ValueError("all window results must belong to the same strategy")
    return next(iter(names))


def _pass_ratio(results: Sequence[WindowMetricResult], policy: RobustnessPolicy) -> Decimal:
    passed = sum(1 for item in results if _window_passes(item, policy))
    return Decimal(passed) / Decimal(len(results))


def _window_passes(item: WindowMetricResult, policy: RobustnessPolicy) -> bool:
    metrics = item.out_of_sample_metrics
    if policy.require_costs_included and not metrics.costs_included:
        return False
    return (
        metrics.net_return >= policy.min_average_oos_return
        and metrics.max_drawdown <= policy.max_oos_drawdown
        and metrics.tail_loss >= -policy.max_tail_loss
        and metrics.profit_factor >= policy.min_profit_factor
        and item.active_quality.is_trusted
    )


def _rejection_reasons(
    results: Sequence[WindowMetricResult],
    *,
    pass_ratio: Decimal,
    average_oos_return: Decimal,
    worst_oos_drawdown: Decimal,
    average_gap: Decimal,
    parameter_stability: Decimal,
    regime_coverage: Mapping[str, int],
    required_regime: str | None,
    policy: RobustnessPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if len(results) < policy.min_windows:
        reasons.append("insufficient validation windows")
    if pass_ratio < policy.min_pass_ratio:
        reasons.append("out-of-sample pass ratio is below threshold")
    if average_oos_return < policy.min_average_oos_return:
        reasons.append("average out-of-sample return is below threshold")
    if worst_oos_drawdown > policy.max_oos_drawdown:
        reasons.append("out-of-sample drawdown exceeds limit")
    if any(item.out_of_sample_metrics.tail_loss < -policy.max_tail_loss for item in results):
        reasons.append("out-of-sample tail loss exceeds limit")
    if policy.require_costs_included and any(
        not item.out_of_sample_metrics.costs_included for item in results
    ):
        reasons.append("fees and slippage must be included in every window")
    if average_gap > policy.max_train_test_return_gap:
        reasons.append("train/test performance gap suggests overfitting")
    if parameter_stability < policy.min_parameter_stability:
        reasons.append("parameter stability is below threshold")
    if any(not item.active_quality.is_trusted for item in results):
        reasons.append("validation window quality is not trusted")
    if required_regime:
        regime_periods = regime_coverage.get(required_regime, 0)
        if regime_periods < policy.min_regime_periods:
            reasons.append("required regime has insufficient out-of-sample coverage")
    return tuple(reasons)


def _quality(
    results: Sequence[WindowMetricResult],
    reasons: tuple[str, ...],
    checked_at: datetime,
    strategy_name: str,
) -> DataQualityStatus:
    issues = [issue for item in results for issue in item.active_quality.issues]
    issues.extend(
        DataQualityIssue(
            flag="walk_forward_rejection",
            severity=DataTrustLevel.DEGRADED,
            reason=reason,
        )
        for reason in reasons
    )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust = DataTrustLevel.REJECTED
    elif issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=tuple(issues),
        source_ref=f"walk_forward:{strategy_name}",
        checked_at=checked_at,
    )


def _total_score(
    *,
    pass_ratio: Decimal,
    average_oos_return: Decimal,
    worst_oos_drawdown: Decimal,
    average_gap: Decimal,
    parameter_stability: Decimal,
    policy: RobustnessPolicy,
) -> Decimal:
    return _clamp(
        (
            pass_ratio
            + _return_score(average_oos_return)
            + (DECIMAL_ONE - _drawdown_ratio(worst_oos_drawdown, policy.max_oos_drawdown))
            + (DECIMAL_ONE - _gap_ratio(average_gap, policy.max_train_test_return_gap))
            + parameter_stability
        )
        / Decimal("5")
    )


def _parameter_stability(results: Sequence[WindowMetricResult]) -> Decimal:
    keys = sorted({key for result in results for key in result.parameters})
    if not keys:
        return DECIMAL_ONE
    scores: list[Decimal] = []
    for key in keys:
        values = tuple(result.parameters.get(key) for result in results)
        numeric_values_list: list[Decimal] = []
        for value in values:
            numeric_value = _as_decimal(value)
            if numeric_value is not None:
                numeric_values_list.append(numeric_value)
        numeric_values = tuple(numeric_values_list)
        if len(numeric_values) == len(values):
            span = max(numeric_values) - min(numeric_values)
            baseline = max(abs(value) for value in numeric_values) or DECIMAL_ONE
            scores.append(DECIMAL_ONE - _clamp(span / baseline))
        else:
            unique_count = len({str(value) for value in values})
            scores.append(DECIMAL_ONE / Decimal(unique_count))
    return _average(tuple(scores))


def _regime_coverage(results: Sequence[WindowMetricResult]) -> dict[str, int]:
    coverage: dict[str, int] = {}
    for result in results:
        for item in result.out_of_sample_metrics.regime_performance:
            coverage[item.regime_label] = coverage.get(item.regime_label, 0) + item.period_count
    return dict(sorted(coverage.items()))


def _average_train_test_gap(results: Sequence[WindowMetricResult]) -> Decimal:
    gaps = tuple(
        max(DECIMAL_ZERO, item.in_sample_metrics.net_return - item.out_of_sample_metrics.net_return)
        for item in results
    )
    return _average(gaps)


def _evidence(
    results: Sequence[WindowMetricResult],
    *,
    pass_ratio: Decimal,
    average_oos_return: Decimal,
    worst_oos_drawdown: Decimal,
    average_gap: Decimal,
    parameter_stability: Decimal,
    required_regime: str | None,
) -> tuple[str, ...]:
    return (
        f"strategy={results[0].strategy_name}",
        f"window_count={len(results)}",
        f"pass_ratio={pass_ratio}",
        f"average_oos_return={average_oos_return}",
        f"worst_oos_drawdown={worst_oos_drawdown}",
        f"average_train_test_return_gap={average_gap}",
        f"parameter_stability={parameter_stability}",
        f"required_regime={required_regime or 'none'}",
        "windows=" + "|".join(str(item.window.index) for item in results),
    )


def _average(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return DECIMAL_ZERO
    return sum(values, DECIMAL_ZERO) / Decimal(len(values))


def _return_score(value: Decimal) -> Decimal:
    return _clamp((value + Decimal("0.05")) / Decimal("0.15"))


def _drawdown_ratio(value: Decimal, cap: Decimal) -> Decimal:
    if cap == DECIMAL_ZERO:
        return DECIMAL_ONE if value > DECIMAL_ZERO else DECIMAL_ZERO
    return _clamp(value / cap)


def _gap_ratio(value: Decimal, cap: Decimal) -> Decimal:
    if cap == DECIMAL_ZERO:
        return DECIMAL_ONE if value > DECIMAL_ZERO else DECIMAL_ZERO
    return _clamp(value / cap)


def _as_decimal(value: Decimal | str | int | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _clamp(value: Decimal) -> Decimal:
    return min(DECIMAL_ONE, max(DECIMAL_ZERO, value))


def regime_periods(metrics: PerformanceMetrics, regime_label: str) -> int:
    """Return out-of-sample periods observed for one regime label."""

    return sum(
        item.period_count
        for item in metrics.regime_performance
        if _matches_regime(item, regime_label)
    )


def _matches_regime(item: RegimePerformance, regime_label: str) -> bool:
    return item.regime_label == regime_label
