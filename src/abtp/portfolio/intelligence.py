"""Advisory portfolio intelligence and hedging recommendations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.portfolio.allocation import AllocationInput, AllocationPolicy, recommend_allocation
from abtp.portfolio.rebalancing import PortfolioAllocationRecommendation

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


class PortfolioHealth(StrEnum):
    """Advisory portfolio-health state."""

    HEALTHY = "healthy"
    WATCH = "watch"
    DEFENSIVE = "defensive"
    REBALANCE_REVIEW = "rebalance_review"
    UNKNOWN = "unknown"


class HedgeRecommendation(StrEnum):
    """Advisory hedge posture without execution authority."""

    NONE = "none"
    RAISE_CASH = "raise_cash"
    INCREASE_STABLECOINS = "increase_stablecoins"
    REDUCE_EXPOSURE = "reduce_exposure"
    DIVERSIFY = "diversify"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True, slots=True)
class PortfolioIntelligencePolicy:
    """Conservative Stage 059 portfolio-intelligence limits."""

    allocation_policy: AllocationPolicy = field(
        default_factory=lambda: AllocationPolicy(policy_version="stage-059.allocation.v1")
    )
    min_cash_reserve_pct: Decimal = Decimal("0.20")
    defensive_cash_target_pct: Decimal = Decimal("0.35")
    stablecoin_target_pct: Decimal = Decimal("0.25")
    max_asset_exposure_pct: Decimal = Decimal("0.40")
    max_sector_exposure_pct: Decimal = Decimal("0.50")
    max_correlation: Decimal = Decimal("0.80")
    high_portfolio_risk: Decimal = Decimal("0.65")
    min_diversification_score: Decimal = Decimal("0.45")
    min_confidence: Decimal = Decimal("0.40")
    policy_version: str = "stage-059.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("min_cash_reserve_pct", self.min_cash_reserve_pct),
            ("defensive_cash_target_pct", self.defensive_cash_target_pct),
            ("stablecoin_target_pct", self.stablecoin_target_pct),
            ("max_asset_exposure_pct", self.max_asset_exposure_pct),
            ("max_sector_exposure_pct", self.max_sector_exposure_pct),
            ("max_correlation", self.max_correlation),
            ("high_portfolio_risk", self.high_portfolio_risk),
            ("min_diversification_score", self.min_diversification_score),
            ("min_confidence", self.min_confidence),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.defensive_cash_target_pct < self.min_cash_reserve_pct:
            raise ValueError("defensive_cash_target_pct cannot be below min_cash_reserve_pct")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class PortfolioIntelligenceInput:
    """Inputs for one portfolio intelligence review."""

    allocation_input: AllocationInput
    sector_exposures: Mapping[str, Decimal] = field(default_factory=dict)
    asset_risk_scores: Mapping[str, Decimal] = field(default_factory=dict)
    diversification_score: Decimal = Decimal("0.50")
    defensive_signal_score: Decimal = Decimal("0")
    confidence_score: Decimal = Decimal("0.50")
    quality: DataQualityStatus | None = None
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("diversification_score", self.diversification_score),
            ("defensive_signal_score", self.defensive_signal_score),
            ("confidence_score", self.confidence_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        _validate_weights(self.sector_exposures, "sector_exposures")
        _validate_weights(self.asset_risk_scores, "asset_risk_scores")
        object.__setattr__(
            self,
            "sector_exposures",
            {key.strip().lower(): value for key, value in self.sector_exposures.items()},
        )
        object.__setattr__(
            self,
            "asset_risk_scores",
            {key.strip().upper(): value for key, value in self.asset_risk_scores.items()},
        )
        if self.generated_at is not None:
            object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))

    @property
    def checked_at(self) -> datetime:
        return self.generated_at or self.allocation_input.generated_at

    @property
    def source_quality(self) -> DataQualityStatus:
        return self.quality or self.allocation_input.data_quality


@dataclass(frozen=True, slots=True)
class PortfolioIntelligenceReport:
    """Advisory portfolio health, hedge, and allocation-plan report."""

    generated_at: datetime
    health: PortfolioHealth
    health_score: Decimal
    hedge_recommendation: HedgeRecommendation
    hedge_pct: Decimal
    recommended_cash_reserve_pct: Decimal
    recommended_stablecoin_pct: Decimal
    diversification_score: Decimal
    max_asset_exposure_pct: Decimal
    max_sector_exposure_pct: Decimal
    max_correlation: Decimal
    allocation_plan: PortfolioAllocationRecommendation
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    evidence: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    limitations: tuple[str, ...] = (
        "Portfolio intelligence and hedging output is advisory context only.",
        "Hedge recommendations mean cash, stablecoin, diversification, or exposure review.",
        "No derivatives, futures, margin, options, or executable hedge orders are created.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by portfolio intelligence.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "health", PortfolioHealth(self.health))
        object.__setattr__(
            self, "hedge_recommendation", HedgeRecommendation(self.hedge_recommendation)
        )
        for name, value in (
            ("health_score", self.health_score),
            ("hedge_pct", self.hedge_pct),
            ("recommended_cash_reserve_pct", self.recommended_cash_reserve_pct),
            ("recommended_stablecoin_pct", self.recommended_stablecoin_pct),
            ("diversification_score", self.diversification_score),
            ("max_asset_exposure_pct", self.max_asset_exposure_pct),
            ("max_sector_exposure_pct", self.max_sector_exposure_pct),
            ("max_correlation", self.max_correlation),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.reasons:
            raise ValueError("portfolio intelligence report requires reasons")
        if not self.evidence:
            raise ValueError("portfolio intelligence report requires evidence")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("portfolio intelligence limitations are required")

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def acceptable_for_review(self) -> bool:
        return not self.rejection_reasons and self.quality.is_trusted

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "health": self.health.value,
            "health_score": str(self.health_score),
            "hedge_recommendation": self.hedge_recommendation.value,
            "hedge_pct": str(self.hedge_pct),
            "recommended_cash_reserve_pct": str(self.recommended_cash_reserve_pct),
            "recommended_stablecoin_pct": str(self.recommended_stablecoin_pct),
            "diversification_score": str(self.diversification_score),
            "max_asset_exposure_pct": str(self.max_asset_exposure_pct),
            "max_sector_exposure_pct": str(self.max_sector_exposure_pct),
            "max_correlation": str(self.max_correlation),
            "allocation_plan": self.allocation_plan.as_dict(),
            "reasons": list(self.reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "evidence": list(self.evidence),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "health": self.health.value,
            "health_score": str(self.health_score),
            "hedge_recommendation": self.hedge_recommendation.value,
            "hedge_pct": str(self.hedge_pct),
            "recommended_cash_reserve_pct": str(self.recommended_cash_reserve_pct),
            "recommended_stablecoin_pct": str(self.recommended_stablecoin_pct),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("portfolio intelligence cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("portfolio intelligence cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("portfolio intelligence cannot submit orders")


def evaluate_portfolio_intelligence(
    inputs: PortfolioIntelligenceInput,
    *,
    policy: PortfolioIntelligencePolicy | None = None,
) -> PortfolioIntelligenceReport:
    """Return advisory portfolio health, hedge, and allocation recommendations."""

    active_policy = policy or PortfolioIntelligencePolicy()
    allocation_plan = recommend_allocation(
        inputs.allocation_input, policy=active_policy.allocation_policy
    )
    max_asset_exposure = _max_asset_exposure(inputs)
    max_sector_exposure = max(inputs.sector_exposures.values(), default=DECIMAL_ZERO)
    max_correlation = _max_correlation(inputs)
    max_asset_risk = max(inputs.asset_risk_scores.values(), default=DECIMAL_ZERO)
    cash_reserve_pct = inputs.allocation_input.available_cash / inputs.allocation_input.total_equity
    health_score = _health_score(
        inputs,
        allocation_plan=allocation_plan,
        max_asset_exposure=max_asset_exposure,
        max_sector_exposure=max_sector_exposure,
        max_correlation=max_correlation,
        max_asset_risk=max_asset_risk,
        cash_reserve_pct=cash_reserve_pct,
    )
    rejection_reasons, issues = _safety_reasons(
        inputs,
        allocation_plan=allocation_plan,
        policy=active_policy,
        max_asset_exposure=max_asset_exposure,
        max_sector_exposure=max_sector_exposure,
        max_correlation=max_correlation,
        max_asset_risk=max_asset_risk,
        cash_reserve_pct=cash_reserve_pct,
    )
    health = _health(health_score, rejection_reasons, allocation_plan)
    hedge = _hedge_recommendation(
        inputs,
        policy=active_policy,
        rejection_reasons=rejection_reasons,
        max_sector_exposure=max_sector_exposure,
        cash_reserve_pct=cash_reserve_pct,
    )
    hedge_pct = _hedge_pct(inputs, active_policy, hedge, cash_reserve_pct)
    recommended_cash = _recommended_cash(active_policy, hedge, cash_reserve_pct)
    recommended_stablecoin = _recommended_stablecoin(active_policy, hedge)
    quality = _quality_status(inputs, allocation_plan, issues, bool(rejection_reasons))
    return PortfolioIntelligenceReport(
        generated_at=inputs.checked_at,
        health=health,
        health_score=health_score,
        hedge_recommendation=hedge,
        hedge_pct=hedge_pct,
        recommended_cash_reserve_pct=recommended_cash,
        recommended_stablecoin_pct=recommended_stablecoin,
        diversification_score=inputs.diversification_score,
        max_asset_exposure_pct=max_asset_exposure,
        max_sector_exposure_pct=max_sector_exposure,
        max_correlation=max_correlation,
        allocation_plan=allocation_plan,
        reasons=_reasons(health, hedge, health_score, cash_reserve_pct),
        rejection_reasons=tuple(dict.fromkeys(rejection_reasons)),
        evidence=_evidence(
            inputs,
            allocation_plan,
            max_asset_exposure,
            max_sector_exposure,
            max_correlation,
            max_asset_risk,
            cash_reserve_pct,
        ),
        quality=quality,
        policy_version=active_policy.policy_version,
    )


def _health_score(
    inputs: PortfolioIntelligenceInput,
    *,
    allocation_plan: PortfolioAllocationRecommendation,
    max_asset_exposure: Decimal,
    max_sector_exposure: Decimal,
    max_correlation: Decimal,
    max_asset_risk: Decimal,
    cash_reserve_pct: Decimal,
) -> Decimal:
    risk = (
        inputs.allocation_input.current_drawdown_pct * Decimal("0.18")
        + max_asset_exposure * Decimal("0.15")
        + max_sector_exposure * Decimal("0.14")
        + max_correlation * Decimal("0.12")
        + max_asset_risk * Decimal("0.15")
        + inputs.defensive_signal_score * Decimal("0.14")
        + (DECIMAL_ONE - inputs.diversification_score) * Decimal("0.08")
        + max(DECIMAL_ZERO, Decimal("0.20") - cash_reserve_pct) * Decimal("0.04")
    )
    if allocation_plan.block_expansion:
        risk += Decimal("0.15")
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, DECIMAL_ONE - risk)).quantize(SCORE_QUANT)


def _safety_reasons(
    inputs: PortfolioIntelligenceInput,
    *,
    allocation_plan: PortfolioAllocationRecommendation,
    policy: PortfolioIntelligencePolicy,
    max_asset_exposure: Decimal,
    max_sector_exposure: Decimal,
    max_correlation: Decimal,
    max_asset_risk: Decimal,
    cash_reserve_pct: Decimal,
) -> tuple[list[str], list[DataQualityIssue]]:
    reasons = list(allocation_plan.rejection_reasons)
    issues = [*inputs.source_quality.issues, *allocation_plan.quality.issues]
    if inputs.source_quality.is_rejected:
        reasons.append("portfolio intelligence source quality is rejected")
        issues.append(_issue("rejected_portfolio_quality", DataTrustLevel.REJECTED, reasons[-1]))
    if cash_reserve_pct < policy.min_cash_reserve_pct:
        reasons.append("cash reserve is below portfolio intelligence floor")
        issues.append(_issue("cash_reserve_breach", DataTrustLevel.REJECTED, reasons[-1]))
    if max_asset_exposure > policy.max_asset_exposure_pct:
        reasons.append("asset exposure exceeds portfolio intelligence limit")
        issues.append(_issue("asset_exposure_breach", DataTrustLevel.REJECTED, reasons[-1]))
    if max_sector_exposure > policy.max_sector_exposure_pct:
        reasons.append("sector exposure exceeds portfolio intelligence limit")
        issues.append(_issue("sector_exposure_breach", DataTrustLevel.REJECTED, reasons[-1]))
    if max_correlation > policy.max_correlation:
        reasons.append("portfolio correlation exceeds intelligence limit")
        issues.append(_issue("correlation_breach", DataTrustLevel.REJECTED, reasons[-1]))
    if max_asset_risk > policy.high_portfolio_risk:
        reasons.append("asset risk exceeds portfolio intelligence limit")
        issues.append(_issue("asset_risk_breach", DataTrustLevel.REJECTED, reasons[-1]))
    if inputs.diversification_score < policy.min_diversification_score:
        reasons.append("diversification score is below floor")
        issues.append(_issue("diversification_breach", DataTrustLevel.DEGRADED, reasons[-1]))
    if inputs.confidence_score < policy.min_confidence:
        reasons.append("portfolio intelligence confidence is below threshold")
        issues.append(_issue("low_confidence", DataTrustLevel.REJECTED, reasons[-1]))
    return reasons, issues


def _health(
    score: Decimal,
    rejection_reasons: list[str],
    allocation_plan: PortfolioAllocationRecommendation,
) -> PortfolioHealth:
    if rejection_reasons:
        return PortfolioHealth.DEFENSIVE
    if allocation_plan.manual_review_required:
        return PortfolioHealth.REBALANCE_REVIEW
    if score >= Decimal("0.75"):
        return PortfolioHealth.HEALTHY
    if score >= Decimal("0.55"):
        return PortfolioHealth.WATCH
    return PortfolioHealth.DEFENSIVE


def _hedge_recommendation(
    inputs: PortfolioIntelligenceInput,
    *,
    policy: PortfolioIntelligencePolicy,
    rejection_reasons: list[str],
    max_sector_exposure: Decimal,
    cash_reserve_pct: Decimal,
) -> HedgeRecommendation:
    if inputs.source_quality.is_rejected:
        return HedgeRecommendation.MANUAL_REVIEW
    if cash_reserve_pct < policy.min_cash_reserve_pct:
        return HedgeRecommendation.RAISE_CASH
    if inputs.defensive_signal_score >= policy.high_portfolio_risk or rejection_reasons:
        return HedgeRecommendation.REDUCE_EXPOSURE
    if max_sector_exposure > policy.max_sector_exposure_pct:
        return HedgeRecommendation.DIVERSIFY
    if cash_reserve_pct < policy.defensive_cash_target_pct:
        return HedgeRecommendation.INCREASE_STABLECOINS
    return HedgeRecommendation.NONE


def _hedge_pct(
    inputs: PortfolioIntelligenceInput,
    policy: PortfolioIntelligencePolicy,
    hedge: HedgeRecommendation,
    cash_reserve_pct: Decimal,
) -> Decimal:
    if hedge is HedgeRecommendation.NONE:
        return DECIMAL_ZERO
    if hedge is HedgeRecommendation.MANUAL_REVIEW:
        return DECIMAL_ONE
    target = max(policy.defensive_cash_target_pct, inputs.defensive_signal_score)
    pct = max(DECIMAL_ZERO, target - cash_reserve_pct)
    return min(DECIMAL_ONE, pct).quantize(SCORE_QUANT)


def _recommended_cash(
    policy: PortfolioIntelligencePolicy,
    hedge: HedgeRecommendation,
    cash_reserve_pct: Decimal,
) -> Decimal:
    if hedge in {HedgeRecommendation.RAISE_CASH, HedgeRecommendation.REDUCE_EXPOSURE}:
        return policy.defensive_cash_target_pct
    return max(cash_reserve_pct, policy.min_cash_reserve_pct).quantize(SCORE_QUANT)


def _recommended_stablecoin(
    policy: PortfolioIntelligencePolicy,
    hedge: HedgeRecommendation,
) -> Decimal:
    if hedge in {HedgeRecommendation.INCREASE_STABLECOINS, HedgeRecommendation.REDUCE_EXPOSURE}:
        return policy.stablecoin_target_pct
    return DECIMAL_ZERO


def _quality_status(
    inputs: PortfolioIntelligenceInput,
    allocation_plan: PortfolioAllocationRecommendation,
    issues: list[DataQualityIssue],
    has_rejections: bool,
) -> DataQualityStatus:
    if has_rejections or any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust = DataTrustLevel.REJECTED
    elif inputs.source_quality.is_degraded or allocation_plan.quality.is_degraded or issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=tuple(issues),
        source_ref="portfolio:intelligence:stage-059",
        checked_at=inputs.checked_at,
    )


def _max_asset_exposure(inputs: PortfolioIntelligenceInput) -> Decimal:
    if inputs.allocation_input.total_equity <= DECIMAL_ZERO:
        return DECIMAL_ZERO
    notionals = [position.valuation for position in inputs.allocation_input.snapshot.positions]
    return max(
        (value / inputs.allocation_input.total_equity for value in notionals), default=DECIMAL_ZERO
    )


def _max_correlation(inputs: PortfolioIntelligenceInput) -> Decimal:
    snapshot = inputs.allocation_input.correlation_snapshot
    if snapshot is None:
        return DECIMAL_ZERO
    return max((abs(item.correlation) for item in snapshot.estimates), default=DECIMAL_ZERO)


def _reasons(
    health: PortfolioHealth,
    hedge: HedgeRecommendation,
    health_score: Decimal,
    cash_reserve_pct: Decimal,
) -> tuple[str, ...]:
    return (
        f"portfolio health is {health.value}",
        f"hedge recommendation is {hedge.value}",
        f"health score is {health_score}",
        f"cash reserve pct is {cash_reserve_pct.quantize(SCORE_QUANT)}",
    )


def _evidence(
    inputs: PortfolioIntelligenceInput,
    allocation_plan: PortfolioAllocationRecommendation,
    max_asset_exposure: Decimal,
    max_sector_exposure: Decimal,
    max_correlation: Decimal,
    max_asset_risk: Decimal,
    cash_reserve_pct: Decimal,
) -> tuple[str, ...]:
    return (
        f"cash_reserve_pct={cash_reserve_pct.quantize(SCORE_QUANT)}",
        f"max_asset_exposure_pct={max_asset_exposure.quantize(SCORE_QUANT)}",
        f"max_sector_exposure_pct={max_sector_exposure.quantize(SCORE_QUANT)}",
        f"max_correlation={max_correlation.quantize(SCORE_QUANT)}",
        f"max_asset_risk={max_asset_risk.quantize(SCORE_QUANT)}",
        f"diversification_score={inputs.diversification_score}",
        f"defensive_signal_score={inputs.defensive_signal_score}",
        f"allocation_block_expansion={allocation_plan.block_expansion}",
    )


def _validate_weights(values: Mapping[str, Decimal], field_name: str) -> None:
    for key, value in values.items():
        if not key.strip():
            raise ValueError(f"{field_name} keys cannot be blank")
        if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
            raise ValueError(f"{field_name} values must be between 0 and 1")


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=flag, severity=severity, reason=reason)
