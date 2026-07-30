"""Deterministic AI model comparison and active-selection recommendations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from abtp.ai.model_registry import (
    ModelApprovalStatus,
    ModelEvaluationSnapshot,
    ModelLifecycleStatus,
    ModelRegistryEntry,
    ModelTrainingRecord,
)
from abtp.config import TradingMode
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class ModelSelectionPolicy:
    """Selection thresholds and live-change safety policy."""

    min_score: Decimal = Decimal("0.55")
    min_accuracy: Decimal = Decimal("0.50")
    min_directional_hit_rate: Decimal = Decimal("0.50")
    max_calibration_error: Decimal = Decimal("0.35")
    min_sample_count: int = 5
    max_evaluation_age: timedelta = timedelta(days=30)
    live_requires_manual_approval: bool = True
    policy_version: str = "stage-042.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("min_score", self.min_score),
            ("min_accuracy", self.min_accuracy),
            ("min_directional_hit_rate", self.min_directional_hit_rate),
            ("max_calibration_error", self.max_calibration_error),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.min_sample_count < 0:
            raise ValueError("min_sample_count cannot be negative")
        if self.max_evaluation_age < timedelta(0):
            raise ValueError("max_evaluation_age cannot be negative")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class ModelSelectionInput:
    """All metadata required to compare one model version."""

    entry: ModelRegistryEntry
    latest_training: ModelTrainingRecord | None
    latest_evaluation: ModelEvaluationSnapshot | None
    current_active: bool = False
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            self.latest_training is not None
            and self.latest_training.model_ref != self.entry.model_ref
        ):
            raise ValueError("training record must match registry entry")
        if (
            self.latest_evaluation is not None
            and self.latest_evaluation.model_ref != self.entry.model_ref
        ):
            raise ValueError("evaluation snapshot must match registry entry")
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class ModelComparisonResult:
    """Explainable comparison score for one model version."""

    model_ref: str
    score: Decimal
    eligible: bool
    rank: int
    rejected_reasons: tuple[str, ...]
    evidence: tuple[str, ...]
    quality: DataQualityStatus
    approval_status: ModelApprovalStatus
    lifecycle_status: ModelLifecycleStatus
    source_refs: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.model_ref.strip():
            raise ValueError("model_ref is required")
        if not DECIMAL_ZERO <= self.score <= DECIMAL_ONE:
            raise ValueError("model comparison score must be between 0 and 1")
        if self.rank <= 0:
            raise ValueError("rank must be positive")
        if not self.evidence:
            raise ValueError("model comparison requires evidence")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "model_ref": self.model_ref,
            "score": str(self.score),
            "eligible": self.eligible,
            "rank": self.rank,
            "rejected_reasons": list(self.rejected_reasons),
            "evidence": list(self.evidence),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "approval_status": self.approval_status.value,
            "lifecycle_status": self.lifecycle_status.value,
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class ActiveModelRecommendation:
    """Advisory active-model selection result."""

    selected_model_ref: str | None
    ranked_models: tuple[ModelComparisonResult, ...]
    generated_at: datetime
    mode: TradingMode
    confidence_score: Decimal
    manual_approval_required: bool
    rejected_reasons: tuple[str, ...]
    downgrade_recommendations: tuple[str, ...]
    can_apply_without_live_swap: bool
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not DECIMAL_ZERO <= self.confidence_score <= DECIMAL_ONE:
            raise ValueError("confidence_score must be between 0 and 1")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def recommended(self) -> bool:
        return self.selected_model_ref is not None and not self.rejected_reasons

    def as_dict(self) -> dict[str, object]:
        return {
            "selected_model_ref": self.selected_model_ref,
            "ranked_models": [result.as_dict() for result in self.ranked_models],
            "generated_at": self.generated_at.isoformat(),
            "mode": self.mode.value,
            "confidence_score": str(self.confidence_score),
            "manual_approval_required": self.manual_approval_required,
            "rejected_reasons": list(self.rejected_reasons),
            "downgrade_recommendations": list(self.downgrade_recommendations),
            "can_apply_without_live_swap": self.can_apply_without_live_swap,
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "selected_model_ref": self.selected_model_ref or "none",
            "ranked_models": "|".join(result.model_ref for result in self.ranked_models),
            "confidence_score": str(self.confidence_score),
            "manual_approval_required": str(self.manual_approval_required),
            "rejected_reasons": "|".join(self.rejected_reasons),
            "downgrade_recommendations": "|".join(self.downgrade_recommendations),
            "policy_version": self.policy_version,
        }


def compare_model_candidates(
    candidates: Sequence[ModelSelectionInput],
    *,
    generated_at: datetime,
    policy: ModelSelectionPolicy | None = None,
) -> tuple[ModelComparisonResult, ...]:
    """Score model versions and return stable ranked comparison results."""

    active_policy = policy or ModelSelectionPolicy()
    compared = tuple(
        _comparison_for(candidate, generated_at=generated_at, policy=active_policy)
        for candidate in candidates
    )
    return tuple(
        _with_rank(result, index + 1)
        for index, result in enumerate(
            sorted(compared, key=lambda item: (-item.score, item.model_ref))
        )
    )


def select_active_model(
    candidates: Sequence[ModelSelectionInput],
    *,
    mode: TradingMode,
    generated_at: datetime,
    manual_approval_for_live_change: bool = False,
    policy: ModelSelectionPolicy | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> ActiveModelRecommendation:
    """Recommend an active model without serving, training, or live swapping it."""

    active_policy = policy or ModelSelectionPolicy()
    ranked = compare_model_candidates(candidates, generated_at=generated_at, policy=active_policy)
    selected = next((item for item in ranked if item.eligible), None)
    reasons: list[str] = []
    if not ranked:
        reasons.append("no model candidates supplied")
    if selected is None:
        reasons.append("no eligible model met selection policy")
    manual_required = mode is TradingMode.LIVE and active_policy.live_requires_manual_approval
    if manual_required and not manual_approval_for_live_change:
        reasons.append("manual approval required before live active-model change")
    downgrade_recommendations = tuple(
        result.model_ref
        for result in ranked
        if result.lifecycle_status is ModelLifecycleStatus.DEGRADED or result.rejected_reasons
    )
    confidence = selected.score if selected is not None and not reasons else DECIMAL_ZERO
    quality = _recommendation_quality(ranked, tuple(reasons), generated_at)
    return ActiveModelRecommendation(
        selected_model_ref=selected.model_ref if selected is not None and not reasons else None,
        ranked_models=ranked,
        generated_at=generated_at,
        mode=mode,
        confidence_score=confidence,
        manual_approval_required=manual_required,
        rejected_reasons=tuple(dict.fromkeys(reasons)),
        downgrade_recommendations=downgrade_recommendations,
        can_apply_without_live_swap=mode
        in {TradingMode.RESEARCH, TradingMode.BACKTEST, TradingMode.PAPER}
        and selected is not None
        and not reasons,
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=source_refs or {},
    )


def _comparison_for(
    candidate: ModelSelectionInput,
    *,
    generated_at: datetime,
    policy: ModelSelectionPolicy,
) -> ModelComparisonResult:
    score = _score(candidate)
    reasons = _rejection_reasons(candidate, generated_at=generated_at, policy=policy, score=score)
    quality = _comparison_quality(candidate, reasons, generated_at)
    return ModelComparisonResult(
        model_ref=candidate.entry.model_ref,
        score=score,
        eligible=not reasons and quality.is_trusted,
        rank=1,
        rejected_reasons=tuple(dict.fromkeys(reasons)),
        evidence=_evidence(candidate, score),
        quality=quality,
        approval_status=candidate.entry.approval_status,
        lifecycle_status=candidate.entry.status,
        source_refs=candidate.source_refs,
    )


def _score(candidate: ModelSelectionInput) -> Decimal:
    evaluation = candidate.latest_evaluation
    if evaluation is None:
        return DECIMAL_ZERO
    metrics = evaluation.metrics
    accuracy = _metric(metrics, "accuracy")
    hit_rate = _metric(metrics, "directional_hit_rate")
    precision = _metric(metrics, "precision_up")
    recall = _metric(metrics, "recall_up")
    calibration = DECIMAL_ONE - _metric(metrics, "calibration_error")
    active_bonus = Decimal("0.03") if candidate.current_active else DECIMAL_ZERO
    lifecycle_penalty = (
        Decimal("0.25") if candidate.entry.status is ModelLifecycleStatus.DEGRADED else DECIMAL_ZERO
    )
    return _clamp(
        accuracy * Decimal("0.25")
        + hit_rate * Decimal("0.25")
        + precision * Decimal("0.15")
        + recall * Decimal("0.15")
        + calibration * Decimal("0.20")
        + active_bonus
        - lifecycle_penalty
    )


def _rejection_reasons(
    candidate: ModelSelectionInput,
    *,
    generated_at: datetime,
    policy: ModelSelectionPolicy,
    score: Decimal,
) -> tuple[str, ...]:
    reasons: list[str] = []
    entry = candidate.entry
    training = candidate.latest_training
    evaluation = candidate.latest_evaluation
    if not entry.selectable:
        reasons.append(f"model lifecycle status is {entry.status.value}")
    if entry.approval_status is ModelApprovalStatus.UNAPPROVED:
        reasons.append("model is not approved for selection")
    if training is None:
        reasons.append("training history is missing")
    elif training.sample_count < policy.min_sample_count:
        reasons.append("training sample count is below threshold")
    if evaluation is None:
        reasons.append("evaluation snapshot is missing")
    else:
        if generated_at - evaluation.evaluated_at > policy.max_evaluation_age:
            reasons.append("evaluation snapshot is stale")
        if not evaluation.quality.is_trusted:
            reasons.append("evaluation quality is not trusted")
        if _metric(evaluation.metrics, "accuracy") < policy.min_accuracy:
            reasons.append("accuracy is below threshold")
        if _metric(evaluation.metrics, "directional_hit_rate") < policy.min_directional_hit_rate:
            reasons.append("directional hit rate is below threshold")
        if _metric(evaluation.metrics, "calibration_error") > policy.max_calibration_error:
            reasons.append("calibration error exceeds threshold")
    if score < policy.min_score:
        reasons.append("model comparison score is below threshold")
    return tuple(reasons)


def _comparison_quality(
    candidate: ModelSelectionInput,
    reasons: tuple[str, ...],
    checked_at: datetime,
) -> DataQualityStatus:
    issues = (
        list(candidate.latest_evaluation.quality.issues)
        if candidate.latest_evaluation is not None
        else []
    )
    issues.extend(
        DataQualityIssue(
            flag="model_selection_rejection",
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
        source_ref=f"model_selection:{candidate.entry.model_ref}",
        checked_at=checked_at,
    )


def _recommendation_quality(
    ranked: Sequence[ModelComparisonResult],
    reasons: tuple[str, ...],
    checked_at: datetime,
) -> DataQualityStatus:
    issues = [issue for result in ranked for issue in result.quality.issues]
    issues.extend(
        DataQualityIssue(
            flag="active_model_selection_rejection",
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
        source_ref="model_selection:active_recommendation",
        checked_at=checked_at,
    )


def _with_rank(result: ModelComparisonResult, rank: int) -> ModelComparisonResult:
    return ModelComparisonResult(
        model_ref=result.model_ref,
        score=result.score,
        eligible=result.eligible,
        rank=rank,
        rejected_reasons=result.rejected_reasons,
        evidence=result.evidence,
        quality=result.quality,
        approval_status=result.approval_status,
        lifecycle_status=result.lifecycle_status,
        source_refs=result.source_refs,
    )


def _evidence(candidate: ModelSelectionInput, score: Decimal) -> tuple[str, ...]:
    evaluation = candidate.latest_evaluation
    training = candidate.latest_training
    directional_hit_rate = (
        _metric(evaluation.metrics, "directional_hit_rate") if evaluation else DECIMAL_ZERO
    )
    calibration_error = (
        _metric(evaluation.metrics, "calibration_error") if evaluation else DECIMAL_ZERO
    )
    return (
        f"model_ref={candidate.entry.model_ref}",
        f"status={candidate.entry.status.value}",
        f"approval={candidate.entry.approval_status.value}",
        f"feature_schema_version={candidate.entry.feature_schema_version}",
        f"sample_count={training.sample_count if training else 0}",
        f"accuracy={_metric(evaluation.metrics, 'accuracy') if evaluation else 0}",
        f"directional_hit_rate={directional_hit_rate}",
        f"calibration_error={calibration_error}",
        f"score={score}",
    )


def _metric(metrics: Mapping[str, Decimal], name: str) -> Decimal:
    return _clamp(metrics.get(name, DECIMAL_ZERO))


def _clamp(value: Decimal) -> Decimal:
    return min(DECIMAL_ONE, max(DECIMAL_ZERO, value))
