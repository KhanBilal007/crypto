"""Advisory portfolio allocation optimizer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain import PortfolioSnapshot
from abtp.portfolio.correlation import CorrelationSnapshot
from abtp.portfolio.rebalancing import (
    DECIMAL_ONE,
    DECIMAL_ZERO,
    PortfolioAllocationRecommendation,
    RebalanceAction,
    RebalanceLine,
)


@dataclass(frozen=True, slots=True)
class AllocationPolicy:
    """Conservative allocation limits for spot portfolios."""

    min_cash_reserve_pct: Decimal = Decimal("0.20")
    max_gross_exposure_pct: Decimal = Decimal("0.80")
    max_asset_weight: Decimal = Decimal("0.40")
    max_correlation: Decimal = Decimal("0.80")
    max_drawdown_pct: Decimal = Decimal("0.10")
    max_volatility_pct: Decimal = Decimal("0.08")
    min_confidence: Decimal = Decimal("0.35")
    rebalance_threshold_pct: Decimal = Decimal("0.02")
    policy_version: str = "stage-047.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("min_cash_reserve_pct", self.min_cash_reserve_pct),
            ("max_gross_exposure_pct", self.max_gross_exposure_pct),
            ("max_asset_weight", self.max_asset_weight),
            ("max_correlation", self.max_correlation),
            ("max_drawdown_pct", self.max_drawdown_pct),
            ("max_volatility_pct", self.max_volatility_pct),
            ("min_confidence", self.min_confidence),
            ("rebalance_threshold_pct", self.rebalance_threshold_pct),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_gross_exposure_pct > DECIMAL_ONE - self.min_cash_reserve_pct:
            raise ValueError("max_gross_exposure_pct must preserve the minimum cash reserve")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class AllocationInput:
    """Inputs for one deterministic allocation review."""

    snapshot: PortfolioSnapshot
    total_equity: Decimal
    available_cash: Decimal
    target_weights: Mapping[str, Decimal]
    generated_at: datetime
    data_quality: DataQualityStatus
    current_drawdown_pct: Decimal = DECIMAL_ZERO
    confidence_scores: Mapping[str, Decimal] = field(default_factory=dict)
    volatility_by_asset: Mapping[str, Decimal] = field(default_factory=dict)
    liquidity_scores: Mapping[str, Decimal] = field(default_factory=dict)
    regime_label: str = "unknown"
    correlation_snapshot: CorrelationSnapshot | None = None
    monte_carlo_allocation_multiplier: Decimal = DECIMAL_ONE
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.total_equity <= DECIMAL_ZERO:
            raise ValueError("total_equity must be positive")
        if self.available_cash < DECIMAL_ZERO:
            raise ValueError("available_cash cannot be negative")
        if self.current_drawdown_pct < DECIMAL_ZERO:
            raise ValueError("current_drawdown_pct cannot be negative")
        if not self.target_weights:
            raise ValueError("target_weights are required")
        _validate_weights(self.target_weights, "target_weights")
        _validate_weights(self.confidence_scores, "confidence_scores")
        _validate_weights(self.volatility_by_asset, "volatility_by_asset")
        _validate_weights(self.liquidity_scores, "liquidity_scores")
        if not DECIMAL_ZERO <= self.monte_carlo_allocation_multiplier <= DECIMAL_ONE:
            raise ValueError("monte_carlo_allocation_multiplier must be between 0 and 1")
        if not self.regime_label.strip():
            raise ValueError("regime_label is required")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(
            self,
            "target_weights",
            {symbol.upper(): value for symbol, value in self.target_weights.items()},
        )
        object.__setattr__(
            self,
            "confidence_scores",
            {symbol.upper(): value for symbol, value in self.confidence_scores.items()},
        )
        object.__setattr__(
            self,
            "volatility_by_asset",
            {symbol.upper(): value for symbol, value in self.volatility_by_asset.items()},
        )
        object.__setattr__(
            self,
            "liquidity_scores",
            {symbol.upper(): value for symbol, value in self.liquidity_scores.items()},
        )
        object.__setattr__(self, "source_refs", dict(self.source_refs))


def recommend_allocation(
    inputs: AllocationInput,
    *,
    policy: AllocationPolicy | None = None,
) -> PortfolioAllocationRecommendation:
    """Return a deterministic advisory portfolio allocation recommendation."""

    active_policy = policy or AllocationPolicy()
    current_weights = _current_weights(inputs)
    cash_reserve_pct = inputs.available_cash / inputs.total_equity
    rejection_reasons, reduction_reasons = _safety_reasons(inputs, active_policy, cash_reserve_pct)
    block_expansion = bool(rejection_reasons)
    lines = tuple(
        _line_for_asset(
            asset_symbol=symbol,
            inputs=inputs,
            policy=active_policy,
            current_weight=current_weights.get(symbol, DECIMAL_ZERO),
            block_expansion=block_expansion,
            reduction_reasons=reduction_reasons,
        )
        for symbol in sorted(set(inputs.target_weights) | set(current_weights))
    )
    quality = _quality_status(inputs, rejection_reasons, reduction_reasons)
    return PortfolioAllocationRecommendation(
        generated_at=inputs.generated_at,
        total_equity=inputs.total_equity,
        available_cash=inputs.available_cash,
        cash_reserve_pct=cash_reserve_pct,
        recommended_cash_reserve_pct=max(active_policy.min_cash_reserve_pct, cash_reserve_pct),
        lines=lines,
        block_expansion=block_expansion,
        manual_review_required=block_expansion or inputs.data_quality.is_rejected,
        rejection_reasons=rejection_reasons,
        reduction_reasons=reduction_reasons,
        evidence=_evidence(inputs, active_policy, cash_reserve_pct),
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=_source_refs(inputs),
    )


def _line_for_asset(
    *,
    asset_symbol: str,
    inputs: AllocationInput,
    policy: AllocationPolicy,
    current_weight: Decimal,
    block_expansion: bool,
    reduction_reasons: tuple[str, ...],
) -> RebalanceLine:
    raw_target = min(inputs.target_weights.get(asset_symbol, DECIMAL_ZERO), policy.max_asset_weight)
    confidence = inputs.confidence_scores.get(asset_symbol)
    if confidence is not None and confidence < policy.min_confidence:
        raw_target = min(raw_target, current_weight)
    volatility = inputs.volatility_by_asset.get(asset_symbol, DECIMAL_ZERO)
    if volatility > policy.max_volatility_pct:
        raw_target = min(raw_target, current_weight)
    correlation = (
        inputs.correlation_snapshot.max_abs_correlation_for(asset_symbol)
        if inputs.correlation_snapshot is not None
        else DECIMAL_ZERO
    )
    if correlation > policy.max_correlation:
        raw_target = min(raw_target, current_weight)
    recommended_weight = raw_target * inputs.monte_carlo_allocation_multiplier
    if block_expansion and recommended_weight > current_weight:
        recommended_weight = current_weight
    recommended_weight = min(recommended_weight, policy.max_asset_weight)
    current_notional = current_weight * inputs.total_equity
    recommended_notional = recommended_weight * inputs.total_equity
    delta = recommended_notional - current_notional
    action = _action(delta, block_expansion)
    reasons = _line_reasons(
        asset_symbol=asset_symbol,
        current_weight=current_weight,
        recommended_weight=recommended_weight,
        confidence=confidence,
        volatility=volatility,
        correlation=correlation,
        policy=policy,
        block_expansion=block_expansion,
        reduction_reasons=reduction_reasons,
    )
    return RebalanceLine(
        asset_symbol=asset_symbol,
        current_weight=current_weight,
        target_weight=inputs.target_weights.get(asset_symbol, DECIMAL_ZERO),
        recommended_weight=recommended_weight,
        current_notional=current_notional,
        recommended_notional=recommended_notional,
        notional_delta=delta,
        action=action,
        reasons=reasons,
        source_refs=inputs.source_refs,
    )


def _current_weights(inputs: AllocationInput) -> Mapping[str, Decimal]:
    weights: dict[str, Decimal] = {}
    for position in inputs.snapshot.positions:
        weights[position.asset.symbol] = weights.get(position.asset.symbol, DECIMAL_ZERO) + (
            position.valuation / inputs.total_equity
        )
    return weights


def _safety_reasons(
    inputs: AllocationInput,
    policy: AllocationPolicy,
    cash_reserve_pct: Decimal,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    rejections: list[str] = []
    reductions: list[str] = []
    if inputs.data_quality.is_rejected:
        rejections.append("portfolio allocation data quality is rejected")
    elif inputs.data_quality.is_degraded:
        reductions.append("portfolio allocation data quality is degraded")
    if cash_reserve_pct < policy.min_cash_reserve_pct:
        rejections.append("minimum cash reserve is breached")
    if inputs.current_drawdown_pct > policy.max_drawdown_pct:
        rejections.append("drawdown limit is breached")
    if inputs.regime_label in {"shock", "high_volatility"}:
        reductions.append(f"market regime {inputs.regime_label} reduces allocation")
    if inputs.monte_carlo_allocation_multiplier < DECIMAL_ONE:
        reductions.append("Monte Carlo risk evidence reduces allocation")
    current_gross = sum(_current_weights(inputs).values(), DECIMAL_ZERO)
    if current_gross > policy.max_gross_exposure_pct:
        rejections.append("gross exposure limit is breached")
    return tuple(dict.fromkeys(rejections)), tuple(dict.fromkeys(reductions))


def _line_reasons(
    *,
    asset_symbol: str,
    current_weight: Decimal,
    recommended_weight: Decimal,
    confidence: Decimal | None,
    volatility: Decimal,
    correlation: Decimal,
    policy: AllocationPolicy,
    block_expansion: bool,
    reduction_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if block_expansion and recommended_weight <= current_weight:
        reasons.append("portfolio expansion is blocked by safety gates")
    if confidence is not None and confidence < policy.min_confidence:
        reasons.append(f"{asset_symbol} confidence is below allocation threshold")
    if volatility > policy.max_volatility_pct:
        reasons.append(f"{asset_symbol} volatility exceeds allocation threshold")
    if correlation > policy.max_correlation:
        reasons.append(f"{asset_symbol} correlation exceeds allocation threshold")
    reasons.extend(reduction_reasons)
    if not reasons:
        if abs(recommended_weight - current_weight) <= policy.rebalance_threshold_pct:
            reasons.append("current allocation is within rebalance threshold")
        elif recommended_weight > current_weight:
            reasons.append("recommended allocation is above current weight")
        else:
            reasons.append("recommended allocation is below current weight")
    return tuple(dict.fromkeys(reasons))


def _action(delta: Decimal, block_expansion: bool) -> RebalanceAction:
    if block_expansion and delta > DECIMAL_ZERO:
        return RebalanceAction.BLOCK_EXPANSION
    if delta > DECIMAL_ZERO:
        return RebalanceAction.INCREASE
    if delta < DECIMAL_ZERO:
        return RebalanceAction.REDUCE
    return RebalanceAction.HOLD


def _quality_status(
    inputs: AllocationInput,
    rejection_reasons: tuple[str, ...],
    reduction_reasons: tuple[str, ...],
) -> DataQualityStatus:
    issues = [*inputs.data_quality.issues]
    issues.extend(
        DataQualityIssue(
            flag="allocation_rejection",
            severity=DataTrustLevel.REJECTED,
            reason=reason,
        )
        for reason in rejection_reasons
    )
    issues.extend(
        DataQualityIssue(
            flag="allocation_reduction",
            severity=DataTrustLevel.DEGRADED,
            reason=reason,
        )
        for reason in reduction_reasons
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
        source_ref="portfolio:allocation",
        checked_at=inputs.generated_at,
    )


def _evidence(
    inputs: AllocationInput,
    policy: AllocationPolicy,
    cash_reserve_pct: Decimal,
) -> tuple[str, ...]:
    return (
        f"total_equity={inputs.total_equity}",
        f"available_cash={inputs.available_cash}",
        f"cash_reserve_pct={cash_reserve_pct}",
        f"min_cash_reserve_pct={policy.min_cash_reserve_pct}",
        f"max_gross_exposure_pct={policy.max_gross_exposure_pct}",
        f"current_drawdown_pct={inputs.current_drawdown_pct}",
        f"regime_label={inputs.regime_label}",
        f"monte_carlo_allocation_multiplier={inputs.monte_carlo_allocation_multiplier}",
    )


def _source_refs(inputs: AllocationInput) -> Mapping[str, str]:
    refs = dict(inputs.source_refs)
    refs.setdefault("portfolio_snapshot", inputs.snapshot.source_ref)
    if inputs.correlation_snapshot is not None:
        refs.update(inputs.correlation_snapshot.source_refs)
    return refs


def _validate_weights(values: Mapping[str, Decimal], name: str) -> None:
    for symbol, value in values.items():
        if not symbol.strip():
            raise ValueError(f"{name} symbols are required")
        if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
            raise ValueError(f"{name} values must be between 0 and 1")
