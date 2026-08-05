"""Explainable advisory confidence scoring."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.confidence.reasons import (
    ConfidenceReason,
    ConfidenceRejectionReason,
    quality_from_reasons,
    unique_reason_messages,
)
from abtp.confidence.weights import (
    DECIMAL_ONE,
    DECIMAL_ZERO,
    SCORE_QUANT,
    ConfidenceComponent,
    ConfidenceWeightPolicy,
)
from abtp.data.normalization import normalize_timestamp
from abtp.data.quality import DataQualityStatus
from abtp.domain.models import JsonValue


class ConfidenceStance(StrEnum):
    """Directional stance used only to detect contradictory evidence."""

    SUPPORTIVE = "supportive"
    OPPOSING = "opposing"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ConfidenceComponentInput:
    """One normalized confidence component supplied by upstream modules."""

    component: ConfidenceComponent
    confidence: Decimal
    quality: DataQualityStatus
    source_ref: str
    rationale: str
    stance: ConfidenceStance = ConfidenceStance.NEUTRAL
    stale: bool = False
    live_eligible: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "component", ConfidenceComponent(self.component))
        object.__setattr__(self, "stance", ConfidenceStance(self.stance))
        if not DECIMAL_ZERO <= self.confidence <= DECIMAL_ONE:
            raise ValueError("component confidence must be between 0 and 1")
        if not self.source_ref.strip():
            raise ValueError("component source_ref is required")
        if not self.rationale.strip():
            raise ValueError("component rationale is required")


@dataclass(frozen=True, slots=True)
class ConfidenceContribution:
    """One included or excluded weighted contribution."""

    component: ConfidenceComponent
    raw_confidence: Decimal
    effective_confidence: Decimal
    weight: Decimal
    weighted_contribution: Decimal
    included: bool
    reasons: tuple[str, ...]
    source_ref: str
    stance: ConfidenceStance
    quality: DataQualityStatus | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("raw_confidence", self.raw_confidence),
            ("effective_confidence", self.effective_confidence),
            ("weight", self.weight),
            ("weighted_contribution", self.weighted_contribution),
        ):
            if value < DECIMAL_ZERO:
                raise ValueError(f"{name} cannot be negative")
        if not self.source_ref.strip():
            raise ValueError("contribution source_ref is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "component": self.component.value,
            "raw_confidence": str(self.raw_confidence),
            "effective_confidence": str(self.effective_confidence),
            "weight": str(self.weight),
            "weighted_contribution": str(self.weighted_contribution),
            "included": self.included,
            "reasons": list(self.reasons),
            "source_ref": self.source_ref,
            "stance": self.stance.value,
            "quality": None if self.quality is None else self.quality.trust_level.value,
            "quality_flags": [] if self.quality is None else list(self.quality.flags),
        }


@dataclass(frozen=True, slots=True)
class ConfidenceScoringInput:
    """Inputs for one confidence aggregation pass."""

    generated_at: datetime
    components: Sequence[ConfidenceComponentInput]
    feature_schema_version: str = "unknown"
    exchange_health_blocked: bool = False
    exchange_health_reasons: tuple[str, ...] = ()
    risk_rejected: bool = False
    risk_reasons: tuple[str, ...] = ()
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.feature_schema_version.strip():
            raise ValueError("feature_schema_version is required")
        normalized_components = tuple(self.components)
        seen: set[ConfidenceComponent] = set()
        for component in normalized_components:
            if component.component in seen:
                raise ValueError(f"duplicate confidence component: {component.component.value}")
            seen.add(component.component)
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "components", normalized_components)
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class ConfidenceScoreResult:
    """Final advisory confidence score with explicit contribution evidence."""

    generated_at: datetime
    score: Decimal
    actionable: bool
    contributions: tuple[ConfidenceContribution, ...]
    rejected_reasons: tuple[str, ...]
    non_actionable_reasons: tuple[str, ...]
    included_weight: Decimal
    total_weight: Decimal
    quality: DataQualityStatus
    feature_schema_version: str
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Confidence score is advisory context only.",
        "Confidence cannot create signals, risk decisions, order intents, or execution.",
        "All trading actions must still pass the Strategy Engine and Risk Management Engine.",
        "No profit is guaranteed by confidence scoring.",
    )

    def __post_init__(self) -> None:
        if not DECIMAL_ZERO <= self.score <= DECIMAL_ONE:
            raise ValueError("confidence score must be between 0 and 1")
        if self.included_weight < DECIMAL_ZERO or self.total_weight <= DECIMAL_ZERO:
            raise ValueError("confidence weights are invalid")
        if not self.limitations:
            raise ValueError("confidence score limitations are required")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "score": str(self.score),
            "actionable": self.actionable,
            "contributions": [contribution.as_dict() for contribution in self.contributions],
            "rejected_reasons": list(self.rejected_reasons),
            "non_actionable_reasons": list(self.non_actionable_reasons),
            "included_weight": str(self.included_weight),
            "total_weight": str(self.total_weight),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "feature_schema_version": self.feature_schema_version,
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "score": str(self.score),
            "actionable": str(self.actionable),
            "included_components": "|".join(
                contribution.component.value
                for contribution in self.contributions
                if contribution.included
            ),
            "excluded_components": "|".join(
                contribution.component.value
                for contribution in self.contributions
                if not contribution.included
            ),
            "rejected_reasons": "|".join(self.rejected_reasons),
            "non_actionable_reasons": "|".join(self.non_actionable_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        """Reject strategy-signal authority."""

        raise ValueError("confidence score cannot create signals")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        """Reject order-intent authority."""

        raise ValueError("confidence score cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        """Reject risk-approval authority."""

        raise ValueError("confidence score cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject execution authority."""

        raise ValueError("confidence score cannot submit orders")


def aggregate_confidence(
    inputs: ConfidenceScoringInput,
    *,
    policy: ConfidenceWeightPolicy | None = None,
) -> ConfidenceScoreResult:
    """Aggregate weighted component confidence with conservative rejection rules."""

    active_policy = policy or ConfidenceWeightPolicy()
    by_component = {component.component: component for component in inputs.components}
    contributions: list[ConfidenceContribution] = []
    reasons: list[ConfidenceReason] = []
    inherited_issues = tuple(issue for item in inputs.components for issue in item.quality.issues)

    for component, weight in active_policy.component_weights.items():
        item = by_component.get(component)
        contribution, component_reasons = _contribution_for(component, weight, item, active_policy)
        contributions.append(contribution)
        reasons.extend(component_reasons)

    included_weight = sum(
        (contribution.weight for contribution in contributions if contribution.included),
        DECIMAL_ZERO,
    ).quantize(SCORE_QUANT)
    raw_score = (
        sum(
            (contribution.weighted_contribution for contribution in contributions),
            DECIMAL_ZERO,
        )
        / active_policy.total_weight
    )
    score = raw_score.quantize(SCORE_QUANT)

    reasons.extend(
        _global_reasons(inputs, tuple(contributions), score, included_weight, active_policy)
    )
    quality = quality_from_reasons(
        tuple(reasons),
        checked_at=inputs.generated_at,
        source_ref="confidence:score",
        inherited_issues=inherited_issues,
    )
    rejected_messages = unique_reason_messages(
        tuple(reason for reason in reasons if reason.rejected)
    )
    non_actionable = unique_reason_messages(tuple(reasons))
    actionable = not rejected_messages and not quality.is_rejected
    return ConfidenceScoreResult(
        generated_at=inputs.generated_at,
        score=score,
        actionable=actionable,
        contributions=tuple(contributions),
        rejected_reasons=rejected_messages,
        non_actionable_reasons=non_actionable,
        included_weight=included_weight,
        total_weight=active_policy.total_weight,
        quality=quality,
        feature_schema_version=inputs.feature_schema_version,
        policy_version=active_policy.policy_version,
        source_refs=_source_refs(inputs, tuple(contributions)),
    )


def _contribution_for(
    component: ConfidenceComponent,
    weight: Decimal,
    item: ConfidenceComponentInput | None,
    policy: ConfidenceWeightPolicy,
) -> tuple[ConfidenceContribution, tuple[ConfidenceReason, ...]]:
    if item is None:
        message = f"confidence component {component.value} is missing"
        rejected = policy.is_required(component)
        return (
            ConfidenceContribution(
                component=component,
                raw_confidence=DECIMAL_ZERO,
                effective_confidence=DECIMAL_ZERO,
                weight=weight,
                weighted_contribution=DECIMAL_ZERO,
                included=False,
                reasons=(message,),
                source_ref=f"missing:{component.value}",
                stance=ConfidenceStance.UNKNOWN,
                quality=None,
            ),
            (
                ConfidenceReason(
                    category=ConfidenceRejectionReason.MISSING_REQUIRED_COMPONENT,
                    message=message,
                    rejected=rejected,
                ),
            ),
        )

    exclusion_reasons: list[str] = []
    reason_records: list[ConfidenceReason] = []
    if item.quality.is_rejected:
        message = f"confidence component {component.value} quality is rejected"
        exclusion_reasons.append(message)
        reason_records.append(
            ConfidenceReason(
                category=ConfidenceRejectionReason.REJECTED_COMPONENT_QUALITY,
                message=message,
            )
        )
    if item.stale:
        message = f"confidence component {component.value} is stale"
        exclusion_reasons.append(message)
        reason_records.append(
            ConfidenceReason(category=ConfidenceRejectionReason.STALE_COMPONENT, message=message)
        )
    if not item.live_eligible:
        message = f"confidence component {component.value} is not live-eligible"
        exclusion_reasons.append(message)
        reason_records.append(
            ConfidenceReason(
                category=ConfidenceRejectionReason.NON_LIVE_ELIGIBLE_COMPONENT,
                message=message,
            )
        )

    if exclusion_reasons:
        return (
            ConfidenceContribution(
                component=component,
                raw_confidence=item.confidence,
                effective_confidence=DECIMAL_ZERO,
                weight=weight,
                weighted_contribution=DECIMAL_ZERO,
                included=False,
                reasons=tuple(exclusion_reasons),
                source_ref=item.source_ref,
                stance=item.stance,
                quality=item.quality,
            ),
            tuple(reason_records),
        )

    effective = item.confidence
    reasons: list[str] = [item.rationale]
    if item.quality.is_degraded:
        effective = (effective * policy.degraded_quality_multiplier).quantize(SCORE_QUANT)
        reasons.append(f"confidence component {component.value} quality is degraded")
    return (
        ConfidenceContribution(
            component=component,
            raw_confidence=item.confidence,
            effective_confidence=effective,
            weight=weight,
            weighted_contribution=(effective * weight).quantize(SCORE_QUANT),
            included=True,
            reasons=tuple(reasons),
            source_ref=item.source_ref,
            stance=item.stance,
            quality=item.quality,
        ),
        (),
    )


def _global_reasons(
    inputs: ConfidenceScoringInput,
    contributions: tuple[ConfidenceContribution, ...],
    score: Decimal,
    included_weight: Decimal,
    policy: ConfidenceWeightPolicy,
) -> tuple[ConfidenceReason, ...]:
    reasons: list[ConfidenceReason] = []
    if included_weight < policy.minimum_included_weight:
        reasons.append(
            ConfidenceReason(
                category=ConfidenceRejectionReason.INSUFFICIENT_INCLUDED_WEIGHT,
                message="included confidence evidence is below required weight",
            )
        )
    if score < policy.minimum_actionable_score:
        reasons.append(
            ConfidenceReason(
                category=ConfidenceRejectionReason.LOW_CONFIDENCE,
                message="aggregate confidence is below actionable threshold",
            )
        )
    if _has_component_disagreement(contributions, policy):
        reasons.append(
            ConfidenceReason(
                category=ConfidenceRejectionReason.COMPONENT_DISAGREEMENT,
                message="supportive and opposing confidence components disagree",
            )
        )
    if inputs.exchange_health_blocked:
        reasons.append(
            ConfidenceReason(
                category=ConfidenceRejectionReason.POOR_EXCHANGE_HEALTH,
                message=_joined_or_default(
                    inputs.exchange_health_reasons,
                    "exchange health blocks confidence actionability",
                ),
            )
        )
    if inputs.risk_rejected:
        reasons.append(
            ConfidenceReason(
                category=ConfidenceRejectionReason.HIGH_RISK_CONTEXT,
                message=_joined_or_default(
                    inputs.risk_reasons, "risk context rejects actionability"
                ),
            )
        )
    risk_component = _component(contributions, ConfidenceComponent.RISK_CONTEXT)
    if (
        risk_component is not None
        and risk_component.effective_confidence < policy.low_component_threshold
    ):
        reasons.append(
            ConfidenceReason(
                category=ConfidenceRejectionReason.HIGH_RISK_CONTEXT,
                message="risk context confidence is below safety threshold",
            )
        )
    data_quality_component = _component(contributions, ConfidenceComponent.DATA_QUALITY)
    if (
        data_quality_component is not None
        and data_quality_component.effective_confidence < policy.low_component_threshold
    ):
        reasons.append(
            ConfidenceReason(
                category=ConfidenceRejectionReason.REJECTED_COMPONENT_QUALITY,
                message="data-quality confidence is below safety threshold",
            )
        )
    return tuple(reasons)


def _has_component_disagreement(
    contributions: tuple[ConfidenceContribution, ...],
    policy: ConfidenceWeightPolicy,
) -> bool:
    supportive = any(
        contribution.included
        and contribution.stance is ConfidenceStance.SUPPORTIVE
        and contribution.effective_confidence >= policy.disagreement_threshold
        for contribution in contributions
    )
    opposing = any(
        contribution.included
        and contribution.stance is ConfidenceStance.OPPOSING
        and contribution.effective_confidence >= policy.disagreement_threshold
        for contribution in contributions
    )
    return supportive and opposing


def _component(
    contributions: tuple[ConfidenceContribution, ...],
    component: ConfidenceComponent,
) -> ConfidenceContribution | None:
    for contribution in contributions:
        if contribution.component is component:
            return contribution
    return None


def _joined_or_default(values: tuple[str, ...], default: str) -> str:
    return "; ".join(values) if values else default


def _source_refs(
    inputs: ConfidenceScoringInput,
    contributions: tuple[ConfidenceContribution, ...],
) -> Mapping[str, str]:
    refs = dict(inputs.source_refs)
    for contribution in contributions:
        refs.setdefault(contribution.component.value, contribution.source_ref)
    return refs
