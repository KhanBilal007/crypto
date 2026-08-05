"""Recovery recommendations for reconciliation mismatches."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.reconciliation.checks import (
    MismatchSeverity,
    ReconciliationEntity,
    ReconciliationMismatch,
    ReconciliationSnapshot,
)


class RecoveryAction(StrEnum):
    """Advisory recovery actions after reconciliation."""

    NO_ACTION = "no_action"
    PAUSE_TRADING = "pause_trading"
    MANUAL_REVIEW = "manual_review"
    RECONCILIATION_HOLD = "reconciliation_hold"
    REFRESH_EXCHANGE_STATE = "refresh_exchange_state"
    REPLAY_MISSING_FILL = "replay_missing_fill"
    RESTART_RECOVERY = "restart_recovery"
    API_OUTAGE_HOLD = "api_outage_hold"


@dataclass(frozen=True, slots=True)
class RecoveryRecommendation:
    """One advisory recovery recommendation."""

    action: RecoveryAction
    required: bool
    reasons: tuple[str, ...]
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("recovery recommendation requires reasons")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "required": self.required,
            "reasons": list(self.reasons),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    """Fail-safe reconciliation recovery plan."""

    generated_at: datetime
    recommendations: tuple[RecoveryRecommendation, ...]
    block_new_entries: bool
    manual_review_required: bool
    can_resume: bool
    rationale: str
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if not self.recommendations:
            raise ValueError("recovery plan requires recommendations")
        if not self.rationale.strip():
            raise ValueError("recovery plan rationale is required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "recommendations": [item.as_dict() for item in self.recommendations],
            "block_new_entries": self.block_new_entries,
            "manual_review_required": self.manual_review_required,
            "can_resume": self.can_resume,
            "rationale": self.rationale,
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "block_new_entries": str(self.block_new_entries),
            "manual_review_required": str(self.manual_review_required),
            "can_resume": str(self.can_resume),
            "actions": "|".join(item.action.value for item in self.recommendations),
            "rationale": self.rationale,
            "quality": self.quality.trust_level.value,
            "quality_flags": "|".join(self.quality.flags),
        }


def build_recovery_plan(
    *,
    mismatches: Sequence[ReconciliationMismatch],
    database_snapshot: ReconciliationSnapshot,
    exchange_snapshot: ReconciliationSnapshot,
    generated_at: datetime,
    source_refs: Mapping[str, str] | None = None,
) -> RecoveryPlan:
    """Build an advisory recovery plan without taking exchange actions."""

    checked_at = normalize_timestamp(generated_at)
    refs = dict(database_snapshot.source_refs)
    refs.update(exchange_snapshot.source_refs)
    refs.update(source_refs or {})
    recommendations = _recommendations(
        tuple(mismatches),
        database_snapshot=database_snapshot,
        exchange_snapshot=exchange_snapshot,
        source_refs=refs,
    )
    block_new_entries = any(
        item.required for item in recommendations if item.action is not RecoveryAction.NO_ACTION
    )
    manual_review_required = any(
        item.required
        for item in recommendations
        if item.action
        in {
            RecoveryAction.MANUAL_REVIEW,
            RecoveryAction.RECONCILIATION_HOLD,
            RecoveryAction.REPLAY_MISSING_FILL,
            RecoveryAction.RESTART_RECOVERY,
            RecoveryAction.API_OUTAGE_HOLD,
        }
    )
    quality = _quality(tuple(mismatches), recommendations, checked_at)
    can_resume = not block_new_entries and quality.is_trusted
    return RecoveryPlan(
        generated_at=checked_at,
        recommendations=recommendations,
        block_new_entries=block_new_entries,
        manual_review_required=manual_review_required,
        can_resume=can_resume,
        rationale=(
            "reconciliation matched and no recovery action is required"
            if can_resume
            else "reconciliation found unsafe state; pause or review is recommended"
        ),
        quality=quality,
        source_refs=refs,
    )


def _recommendations(
    mismatches: tuple[ReconciliationMismatch, ...],
    *,
    database_snapshot: ReconciliationSnapshot,
    exchange_snapshot: ReconciliationSnapshot,
    source_refs: Mapping[str, str],
) -> tuple[RecoveryRecommendation, ...]:
    recommendations: list[RecoveryRecommendation] = []
    if exchange_snapshot.outage:
        recommendations.append(
            _recommendation(
                RecoveryAction.API_OUTAGE_HOLD,
                "exchange outage requires holding reconciliation and pausing new entries",
                source_refs,
            )
        )
    if exchange_snapshot.adapter_stale:
        recommendations.append(
            _recommendation(
                RecoveryAction.REFRESH_EXCHANGE_STATE,
                "stale exchange state requires fresh adapter snapshot before continuation",
                source_refs,
            )
        )
    if database_snapshot.restart_marker or exchange_snapshot.restart_marker:
        marker = database_snapshot.restart_marker or exchange_snapshot.restart_marker or "unknown"
        recommendations.append(
            _recommendation(
                RecoveryAction.RESTART_RECOVERY,
                f"restart marker {marker} requires recovery review",
                source_refs,
            )
        )
    if any(mismatch.entity is ReconciliationEntity.FILL for mismatch in mismatches):
        recommendations.append(
            _recommendation(
                RecoveryAction.REPLAY_MISSING_FILL,
                "fill differences require replaying stored fill evidence before continuation",
                source_refs,
            )
        )
    if any(mismatch.blocks_continuation for mismatch in mismatches):
        recommendations.append(
            _recommendation(
                RecoveryAction.RECONCILIATION_HOLD,
                "blocking reconciliation mismatch requires hold",
                source_refs,
            )
        )
        recommendations.append(
            _recommendation(
                RecoveryAction.MANUAL_REVIEW,
                "operator review is required before unsafe state can resume",
                source_refs,
            )
        )
        recommendations.append(
            _recommendation(
                RecoveryAction.PAUSE_TRADING,
                "pause new entries while reconciliation mismatches remain unresolved",
                source_refs,
            )
        )
    if not recommendations:
        recommendations.append(
            RecoveryRecommendation(
                action=RecoveryAction.NO_ACTION,
                required=False,
                reasons=("database and exchange snapshots match within tolerance",),
                source_refs=source_refs,
            )
        )
    seen_actions: set[RecoveryAction] = set()
    unique: list[RecoveryRecommendation] = []
    for recommendation in recommendations:
        if recommendation.action in seen_actions:
            continue
        seen_actions.add(recommendation.action)
        unique.append(recommendation)
    return tuple(unique)


def _recommendation(
    action: RecoveryAction,
    reason: str,
    source_refs: Mapping[str, str],
) -> RecoveryRecommendation:
    return RecoveryRecommendation(
        action=action,
        required=True,
        reasons=(reason,),
        source_refs=source_refs,
    )


def _quality(
    mismatches: tuple[ReconciliationMismatch, ...],
    recommendations: tuple[RecoveryRecommendation, ...],
    checked_at: datetime,
) -> DataQualityStatus:
    issues: list[DataQualityIssue] = []
    for mismatch in mismatches:
        severity = (
            DataTrustLevel.REJECTED
            if mismatch.severity is MismatchSeverity.BLOCKER
            else DataTrustLevel.DEGRADED
        )
        issues.append(
            DataQualityIssue(
                flag=f"reconciliation_{mismatch.entity.value}",
                severity=severity,
                reason=mismatch.reason,
            )
        )
    for recommendation in recommendations:
        if recommendation.required:
            issues.append(
                DataQualityIssue(
                    flag=f"recovery_{recommendation.action.value}",
                    severity=DataTrustLevel.REJECTED,
                    reason="; ".join(recommendation.reasons),
                )
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
        source_ref="reconciliation:recovery",
        checked_at=checked_at,
    )
