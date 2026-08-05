"""Benchmark comparison and laboratory recommendations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from abtp.backtesting import PerformanceMetrics
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.lab.registry import StrategyCatalogueEntry, StrategyCatalogueStatus
from abtp.validation import RobustnessScore

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class StrategyBenchmarkInput:
    """Laboratory benchmark input for one catalogue strategy."""

    entry: StrategyCatalogueEntry
    metrics: PerformanceMetrics
    measured_at: datetime
    robustness: RobustnessScore | None = None
    quality: DataQualityStatus | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "measured_at", normalize_timestamp(self.measured_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def active_quality(self) -> DataQualityStatus:
        if self.quality is not None:
            return self.quality
        return DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref=f"lab:benchmark:{self.entry.key}",
            checked_at=self.measured_at,
        )


@dataclass(frozen=True, slots=True)
class BenchmarkPolicy:
    """Risk-first thresholds for strategy laboratory comparisons."""

    min_score_for_candidate: Decimal = Decimal("0.50")
    min_score_delta_vs_baseline: Decimal = Decimal("0.05")
    max_drawdown: Decimal = Decimal("0.15")
    min_profit_factor: Decimal = Decimal("1")
    require_costs_included: bool = True
    require_walk_forward_acceptance: bool = True
    policy_version: str = "stage-040.v1"

    def __post_init__(self) -> None:
        if not DECIMAL_ZERO <= self.min_score_for_candidate <= DECIMAL_ONE:
            raise ValueError("min_score_for_candidate must be between 0 and 1")
        if self.min_score_delta_vs_baseline < DECIMAL_ZERO:
            raise ValueError("min_score_delta_vs_baseline cannot be negative")
        if not DECIMAL_ZERO <= self.max_drawdown <= DECIMAL_ONE:
            raise ValueError("max_drawdown must be between 0 and 1")
        if self.min_profit_factor < DECIMAL_ZERO:
            raise ValueError("min_profit_factor cannot be negative")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class StrategyBenchmarkResult:
    """Explainable benchmark score for one strategy entry."""

    strategy_key: str
    score: Decimal
    eligible: bool
    rank: int
    baseline_delta: Decimal
    regime_score: Decimal
    rejected_reasons: tuple[str, ...]
    evidence: tuple[str, ...]
    quality: DataQualityStatus
    source_refs: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.strategy_key.strip():
            raise ValueError("strategy_key is required")
        if not DECIMAL_ZERO <= self.score <= DECIMAL_ONE:
            raise ValueError("benchmark score must be between 0 and 1")
        if self.rank <= 0:
            raise ValueError("rank must be positive")
        if not self.evidence:
            raise ValueError("benchmark result requires evidence")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "strategy_key": self.strategy_key,
            "score": str(self.score),
            "eligible": self.eligible,
            "rank": self.rank,
            "baseline_delta": str(self.baseline_delta),
            "regime_score": str(self.regime_score),
            "rejected_reasons": list(self.rejected_reasons),
            "evidence": list(self.evidence),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class StrategyLaboratoryReport:
    """Advisory strategy laboratory comparison report."""

    generated_at: datetime
    regime_label: str
    baseline_key: str
    results: tuple[StrategyBenchmarkResult, ...]
    recommended_strategy_key: str | None
    rejected_reasons: tuple[str, ...]
    policy_version: str
    source_refs: Mapping[str, str]
    limitations: tuple[str, ...] = (
        "Laboratory recommendations are advisory and cannot create orders.",
        "Parameter candidates must pass walk-forward validation before promotion.",
        "Live strategy changes remain blocked unless supervised live controls approve them.",
        "No profit is guaranteed by laboratory comparisons.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "regime_label": self.regime_label,
            "baseline_key": self.baseline_key,
            "results": [result.as_dict() for result in self.results],
            "recommended_strategy_key": self.recommended_strategy_key,
            "rejected_reasons": list(self.rejected_reasons),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "regime_label": self.regime_label,
            "baseline_key": self.baseline_key,
            "recommended_strategy_key": self.recommended_strategy_key or "none",
            "ranked_strategies": "|".join(result.strategy_key for result in self.results),
            "rejected_reasons": "|".join(self.rejected_reasons),
            "policy_version": self.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        """Reject signal creation; the laboratory has no strategy authority."""

        raise ValueError("strategy laboratory cannot create strategy signals")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject order submission; the laboratory has no execution authority."""

        raise ValueError("strategy laboratory cannot submit orders")


def compare_strategies(
    inputs: Sequence[StrategyBenchmarkInput],
    *,
    baseline_key: str,
    regime_label: str,
    generated_at: datetime | None = None,
    policy: BenchmarkPolicy | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> StrategyLaboratoryReport:
    """Compare candidates against a baseline and return advisory lab evidence."""

    active_policy = policy or BenchmarkPolicy()
    if not inputs:
        raise ValueError("benchmark inputs are required")
    if not regime_label.strip():
        raise ValueError("regime_label is required")
    baseline = _baseline_input(inputs, baseline_key)
    baseline_score = _score_input(baseline, regime_label=regime_label, policy=active_policy)
    unranked = [
        _build_result(
            item,
            regime_label=regime_label,
            baseline_score=baseline_score,
            policy=active_policy,
            rank=1,
        )
        for item in inputs
    ]
    ranked = tuple(
        _with_rank(result, index + 1)
        for index, result in enumerate(
            sorted(unranked, key=lambda item: (-item.score, item.strategy_key))
        )
    )
    recommended = next((result for result in ranked if result.eligible), None)
    reasons: list[str] = []
    if recommended is None:
        reasons.append("no laboratory candidate passed benchmark policy")
    return StrategyLaboratoryReport(
        generated_at=generated_at or datetime.now(UTC),
        regime_label=regime_label,
        baseline_key=baseline_key,
        results=ranked,
        recommended_strategy_key=recommended.strategy_key if recommended is not None else None,
        rejected_reasons=tuple(reasons),
        policy_version=active_policy.policy_version,
        source_refs=source_refs or {},
    )


def regime_benchmark_score(metrics: PerformanceMetrics, regime_label: str) -> Decimal:
    """Return deterministic regime fit from performance metrics."""

    matches = tuple(
        item for item in metrics.regime_performance if item.regime_label == regime_label
    )
    if not matches:
        return Decimal("0.20")
    match = matches[0]
    return _clamp((match.win_rate + _expectancy_score(match.expectancy)) / Decimal("2"))


def _baseline_input(
    inputs: Sequence[StrategyBenchmarkInput],
    baseline_key: str,
) -> StrategyBenchmarkInput:
    for item in inputs:
        if item.entry.key == baseline_key:
            return item
    raise KeyError(f"unknown baseline strategy: {baseline_key}")


def _build_result(
    item: StrategyBenchmarkInput,
    *,
    regime_label: str,
    baseline_score: Decimal,
    policy: BenchmarkPolicy,
    rank: int,
) -> StrategyBenchmarkResult:
    score = _score_input(item, regime_label=regime_label, policy=policy)
    reasons = _rejection_reasons(
        item,
        score=score,
        baseline_delta=score - baseline_score,
        regime_label=regime_label,
        policy=policy,
    )
    quality = _quality(item, reasons)
    return StrategyBenchmarkResult(
        strategy_key=item.entry.key,
        score=score,
        eligible=not reasons and quality.is_trusted,
        rank=rank,
        baseline_delta=score - baseline_score,
        regime_score=regime_benchmark_score(item.metrics, regime_label),
        rejected_reasons=tuple(dict.fromkeys(reasons)),
        evidence=_evidence(item, score=score, regime_label=regime_label),
        quality=quality,
        source_refs=item.source_refs,
    )


def _with_rank(result: StrategyBenchmarkResult, rank: int) -> StrategyBenchmarkResult:
    return StrategyBenchmarkResult(
        strategy_key=result.strategy_key,
        score=result.score,
        eligible=result.eligible,
        rank=rank,
        baseline_delta=result.baseline_delta,
        regime_score=result.regime_score,
        rejected_reasons=result.rejected_reasons,
        evidence=result.evidence,
        quality=result.quality,
        source_refs=result.source_refs,
    )


def _score_input(
    item: StrategyBenchmarkInput,
    *,
    regime_label: str,
    policy: BenchmarkPolicy,
) -> Decimal:
    metrics = item.metrics
    robustness_score = (
        item.robustness.total_score if item.robustness is not None else Decimal("0.50")
    )
    status_penalty = Decimal("0") if item.entry.enabled_for_lab else Decimal("0.50")
    raw_score = (
        _clamp(metrics.win_rate) * Decimal("0.18")
        + _expectancy_score(metrics.expectancy) * Decimal("0.16")
        + (DECIMAL_ONE - _drawdown_ratio(metrics.max_drawdown, policy.max_drawdown))
        * Decimal("0.18")
        + _profit_factor_score(metrics.profit_factor) * Decimal("0.14")
        + regime_benchmark_score(metrics, regime_label) * Decimal("0.14")
        + robustness_score * Decimal("0.20")
    )
    return _clamp(raw_score - status_penalty)


def _rejection_reasons(
    item: StrategyBenchmarkInput,
    *,
    score: Decimal,
    baseline_delta: Decimal,
    regime_label: str,
    policy: BenchmarkPolicy,
) -> tuple[str, ...]:
    metrics = item.metrics
    reasons: list[str] = []
    if item.entry.status is StrategyCatalogueStatus.DISABLED:
        reasons.append("strategy is disabled in laboratory catalogue")
    if item.entry.status is StrategyCatalogueStatus.RETIRED:
        reasons.append("strategy is retired in laboratory catalogue")
    if not item.entry.supports_regime(regime_label):
        reasons.append("strategy does not declare suitability for requested regime")
    if policy.require_costs_included and not metrics.costs_included:
        reasons.append("fees and slippage must be included")
    if metrics.max_drawdown > policy.max_drawdown:
        reasons.append("drawdown exceeds laboratory limit")
    if metrics.profit_factor < policy.min_profit_factor:
        reasons.append("profit factor is below laboratory limit")
    if score < policy.min_score_for_candidate:
        reasons.append("laboratory score is below candidate threshold")
    if baseline_delta < policy.min_score_delta_vs_baseline:
        reasons.append("candidate does not improve enough over baseline")
    if policy.require_walk_forward_acceptance and item.robustness is None:
        reasons.append("walk-forward validation evidence is required")
    if item.robustness is not None and not item.robustness.accepted_for_promotion:
        reasons.append("walk-forward validation did not accept strategy")
    if not item.active_quality.is_trusted:
        reasons.append("benchmark input quality is not trusted")
    return tuple(reasons)


def _quality(
    item: StrategyBenchmarkInput,
    reasons: tuple[str, ...],
) -> DataQualityStatus:
    issues = [*item.active_quality.issues]
    issues.extend(
        DataQualityIssue(
            flag="strategy_lab_rejection",
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
        source_ref=f"lab:benchmark:{item.entry.key}",
        checked_at=item.measured_at,
    )


def _evidence(
    item: StrategyBenchmarkInput,
    *,
    score: Decimal,
    regime_label: str,
) -> tuple[str, ...]:
    return (
        f"strategy_key={item.entry.key}",
        f"status={item.entry.status.value}",
        f"family={item.entry.family}",
        f"regime={regime_label}",
        f"net_return={item.metrics.net_return}",
        f"drawdown={item.metrics.max_drawdown}",
        f"profit_factor={item.metrics.profit_factor}",
        f"score={score}",
        "walk_forward_accepted="
        f"{item.robustness.accepted_for_promotion if item.robustness else False}",
    )


def _expectancy_score(value: Decimal) -> Decimal:
    return _clamp((value + Decimal("0.05")) / Decimal("0.10"))


def _drawdown_ratio(value: Decimal, cap: Decimal) -> Decimal:
    if cap == DECIMAL_ZERO:
        return DECIMAL_ONE if value > DECIMAL_ZERO else DECIMAL_ZERO
    return _clamp(value / cap)


def _profit_factor_score(value: Decimal) -> Decimal:
    return _clamp(value / Decimal("3"))


def _clamp(value: Decimal) -> Decimal:
    return min(DECIMAL_ONE, max(DECIMAL_ZERO, value))
