"""Institutional decision intelligence hub.

The hub combines already-produced advisory evidence into one explainable
decision record. It has no strategy, risk-approval, order, exchange, or live
execution authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


class DecisionEvidenceType(StrEnum):
    """Normalized evidence channels consumed by Stage 070."""

    MULTI_TIMEFRAME = "multi_timeframe"
    MARKET_CYCLE = "market_cycle"
    ONCHAIN = "onchain"
    FUNDAMENTAL = "fundamental"
    MACRO_NARRATIVE = "macro_narrative"
    AI_COMMITTEE = "ai_committee"
    PORTFOLIO_STATUS = "portfolio_status"
    RISK_ENGINE = "risk_engine"
    OPPORTUNITY_SCANNER = "opportunity_scanner"
    CONFIDENCE_ENGINE = "confidence_engine"


class DecisionStance(StrEnum):
    """Evidence stance used by the hub to detect support or conflict."""

    SUPPORTIVE = "supportive"
    OPPOSING = "opposing"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class FinalInvestmentDecision(StrEnum):
    """Advisory final decision labels."""

    FAVORABLE_REVIEW = "favorable_review"
    HOLD_REVIEW = "hold_review"
    DEFENSIVE_REVIEW = "defensive_review"
    REJECT_NO_ACTION = "reject_no_action"


@dataclass(frozen=True, slots=True)
class DecisionHubPolicy:
    """Conservative thresholds for final advisory decisions."""

    min_confidence: Decimal = Decimal("0.60")
    min_support_score: Decimal = Decimal("0.60")
    max_risk_score: Decimal = Decimal("0.55")
    base_allocation_pct: Decimal = Decimal("0.05")
    max_suggested_allocation_pct: Decimal = Decimal("0.15")
    require_risk_engine: bool = True
    require_confidence_engine: bool = True
    required_evidence: tuple[DecisionEvidenceType, ...] = (
        DecisionEvidenceType.MULTI_TIMEFRAME,
        DecisionEvidenceType.MARKET_CYCLE,
        DecisionEvidenceType.AI_COMMITTEE,
        DecisionEvidenceType.PORTFOLIO_STATUS,
        DecisionEvidenceType.RISK_ENGINE,
        DecisionEvidenceType.OPPORTUNITY_SCANNER,
        DecisionEvidenceType.CONFIDENCE_ENGINE,
    )
    policy_version: str = "stage-070.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("min_confidence", self.min_confidence),
            ("min_support_score", self.min_support_score),
            ("max_risk_score", self.max_risk_score),
            ("base_allocation_pct", self.base_allocation_pct),
            ("max_suggested_allocation_pct", self.max_suggested_allocation_pct),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.base_allocation_pct > self.max_suggested_allocation_pct:
            raise ValueError("base_allocation_pct cannot exceed max_suggested_allocation_pct")
        if not self.required_evidence:
            raise ValueError("required_evidence is required")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class DecisionEvidence:
    """One normalized evidence item from an upstream advisory module."""

    evidence_type: DecisionEvidenceType
    source_ref: str
    summary: str
    confidence: Decimal
    support_score: Decimal
    risk_score: Decimal
    quality: DataQualityStatus
    stance: DecisionStance = DecisionStance.NEUTRAL
    weight: Decimal = Decimal("1")
    blocking: bool = False
    stale: bool = False
    suggested_holding_period: str | None = None
    details: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_type", DecisionEvidenceType(self.evidence_type))
        object.__setattr__(self, "stance", DecisionStance(self.stance))
        for name, value in (
            ("confidence", self.confidence),
            ("support_score", self.support_score),
            ("risk_score", self.risk_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.weight <= DECIMAL_ZERO:
            raise ValueError("evidence weight must be positive")
        if not self.source_ref.strip():
            raise ValueError("evidence source_ref is required")
        if not self.summary.strip():
            raise ValueError("evidence summary is required")
        object.__setattr__(self, "details", dict(self.details))

    @property
    def usable(self) -> bool:
        return self.quality.is_trusted and not self.stale and not self.blocking

    def as_dict(self) -> dict[str, object]:
        return {
            "evidence_type": self.evidence_type.value,
            "source_ref": self.source_ref,
            "summary": self.summary,
            "confidence": str(self.confidence),
            "support_score": str(self.support_score),
            "risk_score": str(self.risk_score),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "stance": self.stance.value,
            "weight": str(self.weight),
            "blocking": self.blocking,
            "stale": self.stale,
            "suggested_holding_period": self.suggested_holding_period,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class SuggestedAllocation:
    """Advisory allocation context; not an order or capital movement."""

    symbol: str
    suggested_allocation_pct: Decimal
    max_allocation_pct: Decimal
    rationale: str
    requires_risk_engine_approval: bool = True

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        for name, value in (
            ("suggested_allocation_pct", self.suggested_allocation_pct),
            ("max_allocation_pct", self.max_allocation_pct),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.suggested_allocation_pct > self.max_allocation_pct:
            raise ValueError("suggested_allocation_pct cannot exceed max_allocation_pct")
        if not self.rationale.strip():
            raise ValueError("allocation rationale is required")
        object.__setattr__(self, "symbol", self.symbol.upper())

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "suggested_allocation_pct": str(self.suggested_allocation_pct),
            "max_allocation_pct": str(self.max_allocation_pct),
            "rationale": self.rationale,
            "requires_risk_engine_approval": self.requires_risk_engine_approval,
        }


@dataclass(frozen=True, slots=True)
class EntryExitPlan:
    """Advisory entry and exit context; not executable order instructions."""

    entry_mode: str
    exit_mode: str
    holding_period: str
    stop_loss_required: bool
    rationale: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.entry_mode.strip():
            raise ValueError("entry_mode is required")
        if not self.exit_mode.strip():
            raise ValueError("exit_mode is required")
        if not self.holding_period.strip():
            raise ValueError("holding_period is required")
        if not self.rationale:
            raise ValueError("entry/exit plan requires rationale")

    def as_dict(self) -> dict[str, object]:
        return {
            "entry_mode": self.entry_mode,
            "exit_mode": self.exit_mode,
            "holding_period": self.holding_period,
            "stop_loss_required": self.stop_loss_required,
            "rationale": list(self.rationale),
        }


@dataclass(frozen=True, slots=True)
class DecisionRiskAssessment:
    """Explainable risk context for the final decision record."""

    risk_score: Decimal
    risk_level: str
    block_new_entries: bool
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not DECIMAL_ZERO <= self.risk_score <= DECIMAL_ONE:
            raise ValueError("risk_score must be between 0 and 1")
        if not self.risk_level.strip():
            raise ValueError("risk_level is required")
        if not self.reasons:
            raise ValueError("risk assessment requires reasons")

    def as_dict(self) -> dict[str, object]:
        return {
            "risk_score": str(self.risk_score),
            "risk_level": self.risk_level,
            "block_new_entries": self.block_new_entries,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class DecisionHubInput:
    """Input bundle for one final advisory decision record."""

    symbol: str
    generated_at: datetime
    evidence: Sequence[DecisionEvidence]
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        normalized_evidence = tuple(self.evidence)
        if not normalized_evidence:
            raise ValueError("decision evidence is required")
        seen: set[DecisionEvidenceType] = set()
        for item in normalized_evidence:
            if item.evidence_type in seen:
                raise ValueError(f"duplicate decision evidence: {item.evidence_type.value}")
            seen.add(item.evidence_type)
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "evidence", normalized_evidence)
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class InstitutionalDecisionRecord:
    """Complete explainable decision record for operator review."""

    symbol: str
    generated_at: datetime
    final_decision: FinalInvestmentDecision
    confidence_score: Decimal
    support_score: Decimal
    allocation: SuggestedAllocation
    holding_period: str
    entry_exit_plan: EntryExitPlan
    risk_assessment: DecisionRiskAssessment
    evidence: tuple[DecisionEvidence, ...]
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Institutional decision intelligence is advisory review context only.",
        "Final decisions cannot create signals, approve risk, create orders, or execute trades.",
        "Suggested allocation and entry/exit plans require future strategy and risk approval.",
        "No exchange, provider, model-serving, or live trading calls are made.",
        "No profit is guaranteed by decision intelligence.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "final_decision", FinalInvestmentDecision(self.final_decision))
        for name, value in (
            ("confidence_score", self.confidence_score),
            ("support_score", self.support_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.reasons:
            raise ValueError("decision record requires reasons")
        if not self.evidence:
            raise ValueError("decision record requires evidence")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def actionable_review(self) -> bool:
        return (
            self.final_decision is FinalInvestmentDecision.FAVORABLE_REVIEW
            and not self.rejection_reasons
            and self.quality.is_trusted
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "generated_at": self.generated_at.isoformat(),
            "final_decision": self.final_decision.value,
            "confidence_score": str(self.confidence_score),
            "support_score": str(self.support_score),
            "allocation": self.allocation.as_dict(),
            "holding_period": self.holding_period,
            "entry_exit_plan": self.entry_exit_plan.as_dict(),
            "risk_assessment": self.risk_assessment.as_dict(),
            "evidence": [item.as_dict() for item in self.evidence],
            "reasons": list(self.reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "symbol": self.symbol,
            "final_decision": self.final_decision.value,
            "confidence_score": str(self.confidence_score),
            "support_score": str(self.support_score),
            "risk_score": str(self.risk_assessment.risk_score),
            "suggested_allocation_pct": str(self.allocation.suggested_allocation_pct),
            "holding_period": self.holding_period,
            "evidence_types": "|".join(item.evidence_type.value for item in self.evidence),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("decision intelligence cannot create strategy signals")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("decision intelligence cannot approve risk")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("decision intelligence cannot create order intents")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("decision intelligence cannot submit orders")

    def execute_trade(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("decision intelligence cannot execute trades")


def build_institutional_decision(
    inputs: DecisionHubInput,
    *,
    policy: DecisionHubPolicy | None = None,
) -> InstitutionalDecisionRecord:
    """Combine platform intelligence into one advisory decision record."""

    active_policy = policy or DecisionHubPolicy()
    evidence = tuple(inputs.evidence)
    rejections = _rejection_reasons(evidence, active_policy)
    support_score = _weighted_average(evidence, "support_score")
    confidence_score = _weighted_average(evidence, "confidence")
    risk_score = _weighted_average(evidence, "risk_score")
    quality = _decision_quality(evidence, rejections, inputs.generated_at)
    risk_assessment = _risk_assessment(evidence, risk_score, rejections, active_policy)
    decision = _final_decision(
        confidence_score=confidence_score,
        support_score=support_score,
        risk_assessment=risk_assessment,
        rejection_reasons=rejections,
        quality=quality,
        policy=active_policy,
    )
    allocation = _allocation(
        symbol=inputs.symbol,
        decision=decision,
        confidence_score=confidence_score,
        support_score=support_score,
        risk_score=risk_score,
        policy=active_policy,
    )
    holding_period = _holding_period(evidence, decision)
    entry_exit_plan = _entry_exit_plan(decision, holding_period, risk_assessment)
    return InstitutionalDecisionRecord(
        symbol=inputs.symbol,
        generated_at=inputs.generated_at,
        final_decision=decision,
        confidence_score=confidence_score,
        support_score=support_score,
        allocation=allocation,
        holding_period=holding_period,
        entry_exit_plan=entry_exit_plan,
        risk_assessment=risk_assessment,
        evidence=evidence,
        reasons=_decision_reasons(evidence, decision, support_score, confidence_score, risk_score),
        rejection_reasons=rejections,
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=inputs.source_refs,
    )


def _rejection_reasons(
    evidence: tuple[DecisionEvidence, ...],
    policy: DecisionHubPolicy,
) -> tuple[str, ...]:
    by_type = {item.evidence_type for item in evidence}
    reasons: list[str] = []
    for required in policy.required_evidence:
        if required not in by_type:
            reasons.append(f"missing required evidence: {required.value}")
    for item in evidence:
        if item.blocking:
            reasons.append(f"{item.evidence_type.value} blocks new decision review")
        if item.stale:
            reasons.append(f"{item.evidence_type.value} evidence is stale")
        if not item.quality.is_trusted:
            reasons.append(f"{item.evidence_type.value} quality is not trusted")
    if policy.require_risk_engine:
        risk = next(
            (item for item in evidence if item.evidence_type is DecisionEvidenceType.RISK_ENGINE),
            None,
        )
        if risk is None or risk.blocking or risk.risk_score > policy.max_risk_score:
            reasons.append("risk engine evidence does not allow favorable review")
    if policy.require_confidence_engine:
        confidence = next(
            (
                item
                for item in evidence
                if item.evidence_type is DecisionEvidenceType.CONFIDENCE_ENGINE
            ),
            None,
        )
        if confidence is None or confidence.confidence < policy.min_confidence:
            reasons.append("confidence engine evidence is below threshold")
    return tuple(dict.fromkeys(reasons))


def _weighted_average(evidence: tuple[DecisionEvidence, ...], field_name: str) -> Decimal:
    usable = tuple(item for item in evidence if item.usable)
    if not usable:
        return DECIMAL_ZERO
    numerator = sum(
        (getattr(item, field_name) * item.weight for item in usable),
        DECIMAL_ZERO,
    )
    denominator = sum((item.weight for item in usable), DECIMAL_ZERO)
    return (numerator / denominator).quantize(SCORE_QUANT)


def _risk_assessment(
    evidence: tuple[DecisionEvidence, ...],
    risk_score: Decimal,
    rejection_reasons: tuple[str, ...],
    policy: DecisionHubPolicy,
) -> DecisionRiskAssessment:
    block = bool(rejection_reasons) or risk_score > policy.max_risk_score
    if block:
        level = "blocked"
    elif risk_score >= Decimal("0.40"):
        level = "elevated"
    else:
        level = "normal"
    risk_items = tuple(
        item for item in evidence if item.evidence_type is DecisionEvidenceType.RISK_ENGINE
    )
    reasons = [
        f"risk_score={risk_score}",
        f"max_allowed_risk_score={policy.max_risk_score}",
        *rejection_reasons,
        *(item.summary for item in risk_items),
    ]
    return DecisionRiskAssessment(
        risk_score=risk_score,
        risk_level=level,
        block_new_entries=block,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _final_decision(
    *,
    confidence_score: Decimal,
    support_score: Decimal,
    risk_assessment: DecisionRiskAssessment,
    rejection_reasons: tuple[str, ...],
    quality: DataQualityStatus,
    policy: DecisionHubPolicy,
) -> FinalInvestmentDecision:
    if rejection_reasons or risk_assessment.block_new_entries or quality.is_rejected:
        return FinalInvestmentDecision.REJECT_NO_ACTION
    if confidence_score < policy.min_confidence or support_score < policy.min_support_score:
        return FinalInvestmentDecision.HOLD_REVIEW
    if risk_assessment.risk_level == "elevated" or quality.is_degraded:
        return FinalInvestmentDecision.DEFENSIVE_REVIEW
    return FinalInvestmentDecision.FAVORABLE_REVIEW


def _allocation(
    *,
    symbol: str,
    decision: FinalInvestmentDecision,
    confidence_score: Decimal,
    support_score: Decimal,
    risk_score: Decimal,
    policy: DecisionHubPolicy,
) -> SuggestedAllocation:
    if decision is not FinalInvestmentDecision.FAVORABLE_REVIEW:
        return SuggestedAllocation(
            symbol=symbol,
            suggested_allocation_pct=DECIMAL_ZERO,
            max_allocation_pct=DECIMAL_ZERO,
            rationale="no allocation suggested unless decision is favorable_review",
        )
    raw = policy.base_allocation_pct * confidence_score * support_score * (DECIMAL_ONE - risk_score)
    suggested = min(policy.max_suggested_allocation_pct, raw).quantize(SCORE_QUANT)
    return SuggestedAllocation(
        symbol=symbol,
        suggested_allocation_pct=suggested,
        max_allocation_pct=policy.max_suggested_allocation_pct,
        rationale=(
            "advisory allocation scaled by confidence, support, and risk; "
            "requires future Risk Management Engine approval"
        ),
    )


def _holding_period(
    evidence: tuple[DecisionEvidence, ...],
    decision: FinalInvestmentDecision,
) -> str:
    if decision is FinalInvestmentDecision.REJECT_NO_ACTION:
        return "none"
    periods = tuple(
        item.suggested_holding_period
        for item in evidence
        if item.usable and item.suggested_holding_period
    )
    return periods[0] if periods else "operator_review_required"


def _entry_exit_plan(
    decision: FinalInvestmentDecision,
    holding_period: str,
    risk_assessment: DecisionRiskAssessment,
) -> EntryExitPlan:
    if decision is FinalInvestmentDecision.FAVORABLE_REVIEW:
        return EntryExitPlan(
            entry_mode="operator_review_then_strategy_signal",
            exit_mode="risk_engine_stop_loss_and_stage_046_exit_review",
            holding_period=holding_period,
            stop_loss_required=True,
            rationale=(
                "favorable review still requires strategy signal generation",
                "future order intent must pass Risk Management Engine",
                "exit plan must be reviewed by position-exit controls",
            ),
        )
    return EntryExitPlan(
        entry_mode="no_new_entry",
        exit_mode="monitor_or_reduce_exposure_review",
        holding_period=holding_period,
        stop_loss_required=True,
        rationale=(
            f"decision={decision.value}",
            f"risk_level={risk_assessment.risk_level}",
            "no executable entry is produced by decision intelligence",
        ),
    )


def _decision_reasons(
    evidence: tuple[DecisionEvidence, ...],
    decision: FinalInvestmentDecision,
    support_score: Decimal,
    confidence_score: Decimal,
    risk_score: Decimal,
) -> tuple[str, ...]:
    return (
        f"decision={decision.value}",
        f"support_score={support_score}",
        f"confidence_score={confidence_score}",
        f"risk_score={risk_score}",
        *tuple(item.summary for item in evidence if item.usable),
    )


def _decision_quality(
    evidence: tuple[DecisionEvidence, ...],
    rejection_reasons: tuple[str, ...],
    generated_at: datetime,
) -> DataQualityStatus:
    issues: list[DataQualityIssue] = []
    for item in evidence:
        issues.extend(item.quality.issues)
        if item.stale:
            issues.append(
                DataQualityIssue(
                    flag="stale_decision_evidence",
                    severity=DataTrustLevel.REJECTED,
                    reason=f"{item.evidence_type.value} evidence is stale",
                )
            )
        if item.blocking:
            issues.append(
                DataQualityIssue(
                    flag="blocking_decision_evidence",
                    severity=DataTrustLevel.REJECTED,
                    reason=f"{item.evidence_type.value} blocks decision review",
                )
            )
    issues.extend(
        DataQualityIssue(
            flag="decision_hub_rejection",
            severity=DataTrustLevel.DEGRADED,
            reason=reason,
        )
        for reason in rejection_reasons
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
        source_ref="intelligence:decision_hub",
        checked_at=normalize_timestamp(generated_at),
    )
