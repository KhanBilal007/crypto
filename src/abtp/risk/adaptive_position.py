"""Advisory adaptive position management for open spot positions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.risk.exits import (
    ExitAction,
    ExitRecommendation,
    PositionExitInput,
    PositionExitPolicy,
    recommend_position_exit,
)

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


class HoldingRecommendation(StrEnum):
    """Advisory position-management recommendation."""

    HOLD = "hold"
    REDUCE = "reduce"
    INCREASE_REVIEW = "increase_review"
    EXIT_REVIEW = "exit_review"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True, slots=True)
class AdaptivePositionPolicy:
    """Conservative thresholds for Stage 058 adaptive position management."""

    exit_policy: PositionExitPolicy = field(
        default_factory=lambda: PositionExitPolicy(policy_version="stage-058.exit.v1")
    )
    low_confidence_threshold: Decimal = Decimal("0.35")
    high_confidence_threshold: Decimal = Decimal("0.72")
    high_risk_threshold: Decimal = Decimal("0.70")
    reduce_risk_threshold: Decimal = Decimal("0.55")
    max_increase_pct: Decimal = Decimal("0.15")
    confidence_reduce_pct: Decimal = Decimal("0.25")
    high_risk_reduce_pct: Decimal = Decimal("0.50")
    max_position_age: timedelta = timedelta(days=21)
    policy_version: str = "stage-058.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("low_confidence_threshold", self.low_confidence_threshold),
            ("high_confidence_threshold", self.high_confidence_threshold),
            ("high_risk_threshold", self.high_risk_threshold),
            ("reduce_risk_threshold", self.reduce_risk_threshold),
            ("max_increase_pct", self.max_increase_pct),
            ("confidence_reduce_pct", self.confidence_reduce_pct),
            ("high_risk_reduce_pct", self.high_risk_reduce_pct),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.low_confidence_threshold >= self.high_confidence_threshold:
            raise ValueError("low_confidence_threshold must be below high_confidence_threshold")
        if self.reduce_risk_threshold >= self.high_risk_threshold:
            raise ValueError("reduce_risk_threshold must be below high_risk_threshold")
        if self.max_position_age < timedelta(0):
            raise ValueError("max_position_age cannot be negative")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class AdaptivePositionInput:
    """Inputs for one advisory adaptive position-management review."""

    exit_input: PositionExitInput
    confidence_score: Decimal
    volatility_score: Decimal
    regime_risk_score: Decimal
    scaling_score: Decimal
    evaluated_at: datetime | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("confidence_score", self.confidence_score),
            ("volatility_score", self.volatility_score),
            ("regime_risk_score", self.regime_risk_score),
            ("scaling_score", self.scaling_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.evaluated_at is not None:
            object.__setattr__(self, "evaluated_at", normalize_timestamp(self.evaluated_at))

    @property
    def generated_at(self) -> datetime:
        return self.evaluated_at or self.exit_input.evaluated_at


@dataclass(frozen=True, slots=True)
class AdaptivePositionRecommendation:
    """Advisory position-management output with no execution authority."""

    asset_symbol: str
    generated_at: datetime
    recommendation: HoldingRecommendation
    current_risk: Decimal
    hold_pct: Decimal
    sell_pct: Decimal
    increase_pct: Decimal
    exit_pct: Decimal
    stop_price: Decimal
    exit_recommendation: ExitRecommendation
    reasons: tuple[str, ...]
    evidence: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    limitations: tuple[str, ...] = (
        "Adaptive position management is advisory context only.",
        "Percentages are recommendations, not executable orders.",
        "It cannot create strategy signals, risk decisions, order intents, or execution.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by adaptive position management.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "recommendation", HoldingRecommendation(self.recommendation))
        if not self.asset_symbol.strip():
            raise ValueError("asset_symbol is required")
        for name, value in (
            ("current_risk", self.current_risk),
            ("hold_pct", self.hold_pct),
            ("sell_pct", self.sell_pct),
            ("increase_pct", self.increase_pct),
            ("exit_pct", self.exit_pct),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.stop_price <= DECIMAL_ZERO:
            raise ValueError("stop_price must be positive")
        if not self.reasons:
            raise ValueError("adaptive position recommendation requires reasons")
        if not self.evidence:
            raise ValueError("adaptive position recommendation requires evidence")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("adaptive position limitations are required")

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def actionable_context(self) -> bool:
        return self.quality.is_trusted and self.recommendation is HoldingRecommendation.HOLD

    def as_dict(self) -> dict[str, object]:
        return {
            "asset_symbol": self.asset_symbol,
            "generated_at": self.generated_at.isoformat(),
            "recommendation": self.recommendation.value,
            "current_risk": str(self.current_risk),
            "hold_pct": str(self.hold_pct),
            "sell_pct": str(self.sell_pct),
            "increase_pct": str(self.increase_pct),
            "exit_pct": str(self.exit_pct),
            "stop_price": str(self.stop_price),
            "exit_recommendation": self.exit_recommendation.as_dict(),
            "reasons": list(self.reasons),
            "evidence": list(self.evidence),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "asset_symbol": self.asset_symbol,
            "recommendation": self.recommendation.value,
            "current_risk": str(self.current_risk),
            "hold_pct": str(self.hold_pct),
            "sell_pct": str(self.sell_pct),
            "increase_pct": str(self.increase_pct),
            "exit_pct": str(self.exit_pct),
            "stop_price": str(self.stop_price),
            "quality": self.quality.trust_level.value,
            "quality_flags": "|".join(self.quality.flags),
            "policy_version": self.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("adaptive position management cannot create signals")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("adaptive position management cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("adaptive position management cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("adaptive position management cannot submit orders")


def manage_adaptive_position(
    inputs: AdaptivePositionInput,
    *,
    policy: AdaptivePositionPolicy | None = None,
) -> AdaptivePositionRecommendation:
    """Return advisory hold/sell/increase/exit percentages for one open position."""

    active_policy = policy or AdaptivePositionPolicy()
    exit_recommendation = recommend_position_exit(
        inputs.exit_input, policy=active_policy.exit_policy
    )
    current_risk = _current_risk(inputs, exit_recommendation, active_policy)
    recommendation, hold_pct, sell_pct, increase_pct, exit_pct, reasons = _recommendation(
        inputs,
        exit_recommendation=exit_recommendation,
        current_risk=current_risk,
        policy=active_policy,
    )
    quality = _quality(inputs, exit_recommendation, recommendation, reasons)
    return AdaptivePositionRecommendation(
        asset_symbol=exit_recommendation.asset_symbol,
        generated_at=inputs.generated_at,
        recommendation=recommendation,
        current_risk=current_risk,
        hold_pct=hold_pct,
        sell_pct=sell_pct,
        increase_pct=increase_pct,
        exit_pct=exit_pct,
        stop_price=exit_recommendation.stop_price,
        exit_recommendation=exit_recommendation,
        reasons=reasons,
        evidence=_evidence(inputs, exit_recommendation, current_risk),
        quality=quality,
        policy_version=active_policy.policy_version,
    )


def _current_risk(
    inputs: AdaptivePositionInput,
    exit_recommendation: ExitRecommendation,
    policy: AdaptivePositionPolicy,
) -> Decimal:
    stop_proximity = _stop_proximity(
        inputs.exit_input.current_price, exit_recommendation.stop_price
    )
    age_risk = _age_risk(inputs.exit_input.holding_period, policy)
    exit_pressure = exit_recommendation.recommended_exit_fraction
    score = (
        inputs.volatility_score * Decimal("0.20")
        + inputs.regime_risk_score * Decimal("0.20")
        + (DECIMAL_ONE - inputs.confidence_score) * Decimal("0.20")
        + stop_proximity * Decimal("0.15")
        + age_risk * Decimal("0.15")
        + exit_pressure * Decimal("0.10")
    )
    if inputs.exit_input.source_quality.is_rejected:
        score = DECIMAL_ONE
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, score)).quantize(SCORE_QUANT)


def _recommendation(
    inputs: AdaptivePositionInput,
    *,
    exit_recommendation: ExitRecommendation,
    current_risk: Decimal,
    policy: AdaptivePositionPolicy,
) -> tuple[HoldingRecommendation, Decimal, Decimal, Decimal, Decimal, tuple[str, ...]]:
    reasons: list[str] = []
    if exit_recommendation.block_holding or exit_recommendation.action in {
        ExitAction.EXIT_POSITION,
        ExitAction.MANUAL_REVIEW,
    }:
        reasons.append("exit optimizer blocks holding or requires manual review")
        return (
            HoldingRecommendation.EXIT_REVIEW,
            DECIMAL_ZERO,
            DECIMAL_ZERO,
            DECIMAL_ZERO,
            DECIMAL_ONE,
            tuple(reasons),
        )
    if current_risk >= policy.high_risk_threshold:
        reasons.append("current risk exceeds high-risk threshold")
        return (
            HoldingRecommendation.EXIT_REVIEW,
            DECIMAL_ZERO,
            DECIMAL_ZERO,
            DECIMAL_ZERO,
            DECIMAL_ONE,
            tuple(reasons),
        )
    sell_pct = exit_recommendation.recommended_exit_fraction
    if inputs.confidence_score < policy.low_confidence_threshold:
        sell_pct = max(sell_pct, policy.confidence_reduce_pct)
        reasons.append("confidence exit threshold recommends reduction")
    if current_risk >= policy.reduce_risk_threshold:
        sell_pct = max(sell_pct, policy.high_risk_reduce_pct)
        reasons.append("current risk recommends reduction")
    if exit_recommendation.action is ExitAction.PARTIAL_PROFIT:
        reasons.append("partial profit recommendation carries into sell percentage")
    if sell_pct > DECIMAL_ZERO:
        hold_pct = DECIMAL_ONE - sell_pct
        return (
            HoldingRecommendation.REDUCE,
            hold_pct.quantize(SCORE_QUANT),
            sell_pct.quantize(SCORE_QUANT),
            DECIMAL_ZERO,
            DECIMAL_ZERO,
            tuple(reasons or ("position reduction recommended",)),
        )
    if _can_increase(inputs, current_risk, policy):
        increase_pct = min(policy.max_increase_pct, inputs.scaling_score * policy.max_increase_pct)
        reasons.append("high confidence and low risk allow increase review")
        return (
            HoldingRecommendation.INCREASE_REVIEW,
            DECIMAL_ONE,
            DECIMAL_ZERO,
            increase_pct.quantize(SCORE_QUANT),
            DECIMAL_ZERO,
            tuple(reasons),
        )
    if exit_recommendation.tighten_stops:
        reasons.append("tightened stop recommended while holding")
    reasons.append("position may be held with advisory controls")
    return (
        HoldingRecommendation.HOLD,
        DECIMAL_ONE,
        DECIMAL_ZERO,
        DECIMAL_ZERO,
        DECIMAL_ZERO,
        tuple(reasons),
    )


def _can_increase(
    inputs: AdaptivePositionInput,
    current_risk: Decimal,
    policy: AdaptivePositionPolicy,
) -> bool:
    return (
        inputs.exit_input.source_quality.is_trusted
        and inputs.confidence_score >= policy.high_confidence_threshold
        and inputs.scaling_score > DECIMAL_ZERO
        and current_risk < policy.reduce_risk_threshold
        and inputs.volatility_score < policy.reduce_risk_threshold
        and inputs.regime_risk_score < policy.reduce_risk_threshold
    )


def _quality(
    inputs: AdaptivePositionInput,
    exit_recommendation: ExitRecommendation,
    recommendation: HoldingRecommendation,
    reasons: tuple[str, ...],
) -> DataQualityStatus:
    issues = list(exit_recommendation.quality.issues)
    if inputs.exit_input.source_quality.is_rejected:
        issues.append(
            DataQualityIssue(
                flag="adaptive_position_rejected_quality",
                severity=DataTrustLevel.REJECTED,
                reason="source quality is rejected",
            )
        )
    elif recommendation in {HoldingRecommendation.EXIT_REVIEW, HoldingRecommendation.MANUAL_REVIEW}:
        issues.append(
            DataQualityIssue(
                flag="adaptive_position_exit_review",
                severity=DataTrustLevel.REJECTED,
                reason="; ".join(reasons),
            )
        )
    elif (
        recommendation is HoldingRecommendation.REDUCE
        or inputs.exit_input.source_quality.is_degraded
    ):
        issues.append(
            DataQualityIssue(
                flag="adaptive_position_degraded",
                severity=DataTrustLevel.DEGRADED,
                reason="adaptive position recommendation is reduction or uses degraded inputs",
            )
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
        source_ref="risk:adaptive_position",
        checked_at=inputs.generated_at,
    )


def _stop_proximity(current_price: Decimal, stop_price: Decimal) -> Decimal:
    if current_price <= DECIMAL_ZERO:
        return DECIMAL_ONE
    distance = max(DECIMAL_ZERO, current_price - stop_price) / current_price
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, DECIMAL_ONE - distance)).quantize(SCORE_QUANT)


def _age_risk(holding_period: timedelta | None, policy: AdaptivePositionPolicy) -> Decimal:
    if holding_period is None or policy.max_position_age.total_seconds() == 0:
        return DECIMAL_ZERO
    ratio = Decimal(str(holding_period / policy.max_position_age))
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, ratio)).quantize(SCORE_QUANT)


def _evidence(
    inputs: AdaptivePositionInput,
    exit_recommendation: ExitRecommendation,
    current_risk: Decimal,
) -> tuple[str, ...]:
    holding_period = inputs.exit_input.holding_period
    age = str(holding_period) if holding_period is not None else "unknown"
    return (
        f"confidence_score={inputs.confidence_score}",
        f"volatility_score={inputs.volatility_score}",
        f"regime_risk_score={inputs.regime_risk_score}",
        f"scaling_score={inputs.scaling_score}",
        f"position_age={age}",
        f"exit_action={exit_recommendation.action.value}",
        f"exit_fraction={exit_recommendation.recommended_exit_fraction}",
        f"stop_price={exit_recommendation.stop_price}",
        f"current_risk={current_risk}",
    )
