"""Deterministic strategy scoring for the AI Strategy Optimiser."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from abtp.backtesting import PerformanceMetrics, RegimePerformance
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class StrategyMetricSnapshot:
    """Metrics and context used to score one strategy candidate."""

    strategy_name: str
    metrics: PerformanceMetrics
    measured_at: datetime
    source: str = "backtest"
    recent_metrics: PerformanceMetrics | None = None
    quality: DataQualityStatus | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy_name.strip():
            raise ValueError("strategy_name is required")
        if not self.source.strip():
            raise ValueError("metric source is required")
        object.__setattr__(self, "measured_at", normalize_timestamp(self.measured_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def active_quality(self) -> DataQualityStatus:
        if self.quality is not None:
            return self.quality
        return DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref=f"optimizer:{self.strategy_name}:{self.source}",
            checked_at=self.measured_at,
        )


@dataclass(frozen=True, slots=True)
class StrategyScoringPolicy:
    """Scoring policy and risk-first rejection thresholds."""

    min_sample_size: int = 5
    max_drawdown: Decimal = Decimal("0.15")
    min_profit_factor: Decimal = Decimal("1")
    min_score_for_recommendation: Decimal = Decimal("0.50")
    require_costs_included: bool = True
    weight_win_rate: Decimal = Decimal("0.18")
    weight_expectancy: Decimal = Decimal("0.14")
    weight_drawdown: Decimal = Decimal("0.18")
    weight_sharpe: Decimal = Decimal("0.12")
    weight_profit_factor: Decimal = Decimal("0.12")
    weight_regime: Decimal = Decimal("0.14")
    weight_stability: Decimal = Decimal("0.07")
    weight_confidence: Decimal = Decimal("0.05")
    policy_version: str = "stage-038.v1"

    def __post_init__(self) -> None:
        if self.min_sample_size < 0:
            raise ValueError("min_sample_size cannot be negative")
        if not DECIMAL_ZERO <= self.max_drawdown <= DECIMAL_ONE:
            raise ValueError("max_drawdown must be between 0 and 1")
        if self.min_profit_factor < DECIMAL_ZERO:
            raise ValueError("min_profit_factor cannot be negative")
        if not DECIMAL_ZERO <= self.min_score_for_recommendation <= DECIMAL_ONE:
            raise ValueError("min_score_for_recommendation must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        weights = (
            self.weight_win_rate,
            self.weight_expectancy,
            self.weight_drawdown,
            self.weight_sharpe,
            self.weight_profit_factor,
            self.weight_regime,
            self.weight_stability,
            self.weight_confidence,
        )
        if any(weight < DECIMAL_ZERO for weight in weights):
            raise ValueError("scoring weights cannot be negative")
        if sum(weights, DECIMAL_ZERO) <= DECIMAL_ZERO:
            raise ValueError("at least one scoring weight must be positive")


@dataclass(frozen=True, slots=True)
class StrategyScore:
    """Explainable score for one strategy candidate."""

    strategy_name: str
    total_score: Decimal
    confidence_score: Decimal
    eligible: bool
    rejected_reasons: tuple[str, ...]
    components: Mapping[str, Decimal]
    evidence: tuple[str, ...]
    source_refs: Mapping[str, str]
    quality: DataQualityStatus
    policy_version: str

    def __post_init__(self) -> None:
        if not self.strategy_name.strip():
            raise ValueError("strategy_name is required")
        if not DECIMAL_ZERO <= self.total_score <= DECIMAL_ONE:
            raise ValueError("total_score must be between 0 and 1")
        if not DECIMAL_ZERO <= self.confidence_score <= DECIMAL_ONE:
            raise ValueError("confidence_score must be between 0 and 1")
        if not self.evidence:
            raise ValueError("strategy score requires evidence")
        object.__setattr__(self, "components", dict(self.components))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "strategy_name": self.strategy_name,
            "total_score": str(self.total_score),
            "confidence_score": str(self.confidence_score),
            "eligible": self.eligible,
            "rejected_reasons": list(self.rejected_reasons),
            "components": {key: str(value) for key, value in self.components.items()},
            "evidence": list(self.evidence),
            "source_refs": dict(self.source_refs),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
        }


def score_strategies(
    candidates: Sequence[StrategyMetricSnapshot],
    *,
    regime_label: str,
    policy: StrategyScoringPolicy | None = None,
) -> tuple[StrategyScore, ...]:
    """Score candidates and return a stable ranked list."""

    active_policy = policy or StrategyScoringPolicy()
    return tuple(
        sorted(
            (
                score_strategy(candidate, regime_label=regime_label, policy=active_policy)
                for candidate in candidates
            ),
            key=lambda item: (-item.total_score, item.strategy_name),
        )
    )


def score_strategy(
    candidate: StrategyMetricSnapshot,
    *,
    regime_label: str,
    policy: StrategyScoringPolicy | None = None,
) -> StrategyScore:
    """Score one strategy candidate with risk-first rejection reasons."""

    active_policy = policy or StrategyScoringPolicy()
    if not regime_label.strip():
        raise ValueError("regime_label is required")
    metrics = candidate.metrics
    components = {
        "win_rate": _clamp(metrics.win_rate),
        "expectancy": _expectancy_score(metrics.expectancy),
        "drawdown": DECIMAL_ONE - _drawdown_ratio(metrics.max_drawdown, active_policy),
        "sharpe": _bounded_ratio(metrics.sharpe_ratio, Decimal("2")),
        "profit_factor": _bounded_ratio(metrics.profit_factor, Decimal("3")),
        "regime": _regime_score(metrics.regime_performance, regime_label),
        "stability": _stability_score(metrics, candidate.recent_metrics),
        "confidence": _confidence_score(metrics),
    }
    weighted_total = _weighted_total(components, active_policy)
    reasons = _rejection_reasons(candidate, regime_label=regime_label, policy=active_policy)
    quality = _score_quality(candidate, reasons)
    eligible = (
        not reasons
        and quality.is_trusted
        and weighted_total >= active_policy.min_score_for_recommendation
    )
    if weighted_total < active_policy.min_score_for_recommendation:
        reasons = (*reasons, "strategy score is below recommendation threshold")
        quality = _score_quality(candidate, reasons)
        eligible = False
    return StrategyScore(
        strategy_name=candidate.strategy_name,
        total_score=weighted_total,
        confidence_score=components["confidence"],
        eligible=eligible,
        rejected_reasons=tuple(dict.fromkeys(reasons)),
        components=components,
        evidence=_evidence(candidate, regime_label=regime_label, components=components),
        source_refs=candidate.source_refs,
        quality=quality,
        policy_version=active_policy.policy_version,
    )


def _weighted_total(
    components: Mapping[str, Decimal],
    policy: StrategyScoringPolicy,
) -> Decimal:
    weighted = (
        components["win_rate"] * policy.weight_win_rate
        + components["expectancy"] * policy.weight_expectancy
        + components["drawdown"] * policy.weight_drawdown
        + components["sharpe"] * policy.weight_sharpe
        + components["profit_factor"] * policy.weight_profit_factor
        + components["regime"] * policy.weight_regime
        + components["stability"] * policy.weight_stability
        + components["confidence"] * policy.weight_confidence
    )
    total_weight = (
        policy.weight_win_rate
        + policy.weight_expectancy
        + policy.weight_drawdown
        + policy.weight_sharpe
        + policy.weight_profit_factor
        + policy.weight_regime
        + policy.weight_stability
        + policy.weight_confidence
    )
    return _clamp(weighted / total_weight)


def _rejection_reasons(
    candidate: StrategyMetricSnapshot,
    *,
    regime_label: str,
    policy: StrategyScoringPolicy,
) -> tuple[str, ...]:
    metrics = candidate.metrics
    reasons: list[str] = []
    if metrics.trade_count < policy.min_sample_size:
        reasons.append("trade sample size is insufficient")
    if policy.require_costs_included and not metrics.costs_included:
        reasons.append("fees and slippage must be included")
    if metrics.max_drawdown > policy.max_drawdown:
        reasons.append("drawdown exceeds optimiser limit")
    if metrics.profit_factor < policy.min_profit_factor:
        reasons.append("profit factor is below optimiser limit")
    if not candidate.active_quality.is_trusted:
        reasons.append("strategy metric quality is not trusted")
    if not _matching_regime(metrics.regime_performance, regime_label):
        reasons.append("current regime has insufficient strategy evidence")
    return tuple(reasons)


def _score_quality(
    candidate: StrategyMetricSnapshot,
    reasons: tuple[str, ...],
) -> DataQualityStatus:
    issues = [*candidate.active_quality.issues]
    issues.extend(
        DataQualityIssue(
            flag="optimizer_rejection",
            severity=DataTrustLevel.DEGRADED,
            reason=reason,
        )
        for reason in reasons
    )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif issues:
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref=f"optimizer:{candidate.strategy_name}",
        checked_at=candidate.measured_at,
    )


def _evidence(
    candidate: StrategyMetricSnapshot,
    *,
    regime_label: str,
    components: Mapping[str, Decimal],
) -> tuple[str, ...]:
    return (
        f"strategy={candidate.strategy_name}",
        f"source={candidate.source}",
        f"regime={regime_label}",
        f"trade_count={candidate.metrics.trade_count}",
        f"win_rate={candidate.metrics.win_rate}",
        f"expectancy={candidate.metrics.expectancy}",
        f"drawdown={candidate.metrics.max_drawdown}",
        f"profit_factor={candidate.metrics.profit_factor}",
        f"regime_score={components['regime']}",
    )


def _regime_score(
    regimes: Sequence[RegimePerformance],
    regime_label: str,
) -> Decimal:
    match = _matching_regime(regimes, regime_label)
    if match is None:
        return Decimal("0.20")
    return _clamp((match.win_rate + _expectancy_score(match.expectancy)) / Decimal("2"))


def _matching_regime(
    regimes: Sequence[RegimePerformance],
    regime_label: str,
) -> RegimePerformance | None:
    for item in regimes:
        if item.regime_label == regime_label and item.period_count > 0:
            return item
    return None


def _stability_score(
    metrics: PerformanceMetrics,
    recent_metrics: PerformanceMetrics | None,
) -> Decimal:
    base = DECIMAL_ONE - _clamp(metrics.max_drawdown + abs(metrics.tail_loss))
    if recent_metrics is None:
        return _clamp(base)
    drift = abs(metrics.win_rate - recent_metrics.win_rate) + abs(
        metrics.expectancy - recent_metrics.expectancy
    )
    return _clamp(base - drift)


def _confidence_score(metrics: PerformanceMetrics) -> Decimal:
    sample_score = _bounded_ratio(Decimal(metrics.trade_count), Decimal("50"))
    cost_score = DECIMAL_ONE if metrics.costs_included else Decimal("0.25")
    return _clamp((sample_score + cost_score + metrics.win_rate) / Decimal("3"))


def _expectancy_score(value: Decimal) -> Decimal:
    return _clamp((value + Decimal("0.05")) / Decimal("0.10"))


def _drawdown_ratio(value: Decimal, policy: StrategyScoringPolicy) -> Decimal:
    if policy.max_drawdown == DECIMAL_ZERO:
        return DECIMAL_ONE if value > DECIMAL_ZERO else DECIMAL_ZERO
    return _clamp(value / policy.max_drawdown)


def _bounded_ratio(value: Decimal, cap: Decimal) -> Decimal:
    if cap <= DECIMAL_ZERO:
        return DECIMAL_ZERO
    return _clamp(value / cap)


def _clamp(value: Decimal) -> Decimal:
    return min(DECIMAL_ONE, max(DECIMAL_ZERO, value))
