"""Execution quality reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.execution.quality import (
    ExecutionObservation,
    ExecutionQualityPolicy,
    ExecutionQualityScore,
    analyze_execution_quality,
)

DECIMAL_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class ExecutionQualityReport:
    """Auditable report for execution quality review."""

    generated_at: datetime
    scores: tuple[ExecutionQualityScore, ...]
    average_quality_score: Decimal
    warning_reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Execution quality reports are read-only risk context.",
        "Poor execution quality may inform future limits but cannot submit or cancel orders.",
        "All future order paths must still pass the Risk Management Engine.",
        "No profit is guaranteed by execution quality analysis.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def acceptable(self) -> bool:
        return not self.rejection_reasons and self.quality.is_trusted

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "scores": [score.as_dict() for score in self.scores],
            "average_quality_score": str(self.average_quality_score),
            "warning_reasons": list(self.warning_reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "order_count": str(len(self.scores)),
            "average_quality_score": str(self.average_quality_score),
            "acceptable": str(self.acceptable),
            "warning_reasons": "|".join(self.warning_reasons),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "policy_version": self.policy_version,
        }

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject order submission; reports have no execution authority."""

        raise ValueError("execution quality report cannot submit orders")

    def cancel_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject order cancellation; reports have no execution authority."""

        raise ValueError("execution quality report cannot cancel orders")


def build_execution_quality_report(
    observations: Sequence[ExecutionObservation],
    *,
    generated_at: datetime | None = None,
    policy: ExecutionQualityPolicy | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> ExecutionQualityReport:
    """Analyze stored execution observations and return a read-only report."""

    if not observations:
        raise ValueError("execution observations are required")
    active_policy = policy or ExecutionQualityPolicy()
    scores = tuple(
        analyze_execution_quality(observation, policy=active_policy) for observation in observations
    )
    warning_reasons = tuple(
        dict.fromkeys(reason for score in scores for reason in score.warning_reasons)
    )
    rejection_reasons = tuple(
        dict.fromkeys(reason for score in scores for reason in score.rejection_reasons)
    )
    checked_at = generated_at or datetime.now(UTC)
    quality = _report_quality(scores, warning_reasons, rejection_reasons, checked_at)
    return ExecutionQualityReport(
        generated_at=checked_at,
        scores=scores,
        average_quality_score=_average(tuple(score.quality_score for score in scores)),
        warning_reasons=warning_reasons,
        rejection_reasons=rejection_reasons,
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=source_refs or {},
    )


def _report_quality(
    scores: Sequence[ExecutionQualityScore],
    warning_reasons: tuple[str, ...],
    rejection_reasons: tuple[str, ...],
    checked_at: datetime,
) -> DataQualityStatus:
    issues: list[DataQualityIssue] = []
    issues.extend(
        DataQualityIssue(
            flag="execution_quality_warning",
            severity=DataTrustLevel.DEGRADED,
            reason=reason,
        )
        for reason in warning_reasons
    )
    issues.extend(
        DataQualityIssue(
            flag="execution_quality_rejection",
            severity=DataTrustLevel.REJECTED,
            reason=reason,
        )
        for reason in rejection_reasons
    )
    if any(score.rejection_reasons for score in scores):
        trust = DataTrustLevel.REJECTED
    elif issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=tuple(issues),
        source_ref="execution:quality_report",
        checked_at=checked_at,
    )


def _average(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return DECIMAL_ZERO
    return sum(values, DECIMAL_ZERO) / Decimal(len(values))
