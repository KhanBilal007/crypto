"""Rejection reason helpers for advisory confidence scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from abtp.data.normalization import normalize_timestamp
from abtp.data.quality import DataQualityIssue, DataQualityStatus, DataTrustLevel


class ConfidenceRejectionReason(StrEnum):
    """Stable rejection reason categories for confidence scoring."""

    MISSING_REQUIRED_COMPONENT = "missing_required_component"
    INSUFFICIENT_INCLUDED_WEIGHT = "insufficient_included_weight"
    REJECTED_COMPONENT_QUALITY = "rejected_component_quality"
    STALE_COMPONENT = "stale_component"
    NON_LIVE_ELIGIBLE_COMPONENT = "non_live_eligible_component"
    COMPONENT_DISAGREEMENT = "component_disagreement"
    POOR_EXCHANGE_HEALTH = "poor_exchange_health"
    HIGH_RISK_CONTEXT = "high_risk_context"
    LOW_CONFIDENCE = "low_confidence"


@dataclass(frozen=True, slots=True)
class ConfidenceReason:
    """One explainable reason attached to a confidence result."""

    category: ConfidenceRejectionReason
    message: str
    rejected: bool = True

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("confidence reason message is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "category": self.category.value,
            "message": self.message,
            "rejected": self.rejected,
        }


def unique_reason_messages(reasons: tuple[ConfidenceReason, ...]) -> tuple[str, ...]:
    """Return stable de-duplicated reason messages."""

    return tuple(dict.fromkeys(reason.message for reason in reasons))


def quality_from_reasons(
    reasons: tuple[ConfidenceReason, ...],
    *,
    checked_at: datetime,
    source_ref: str,
    inherited_issues: tuple[DataQualityIssue, ...] = (),
) -> DataQualityStatus:
    """Build data-quality status from confidence reason records."""

    issues = [
        *inherited_issues,
        *(
            DataQualityIssue(
                flag=f"confidence_{reason.category.value}",
                severity=DataTrustLevel.REJECTED if reason.rejected else DataTrustLevel.DEGRADED,
                reason=reason.message,
            )
            for reason in reasons
        ),
    ]
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust = DataTrustLevel.REJECTED
    elif issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=tuple(issues),
        source_ref=source_ref,
        checked_at=normalize_timestamp(checked_at),
    )
