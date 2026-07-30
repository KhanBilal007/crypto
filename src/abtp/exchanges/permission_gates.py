"""Advisory trading permission gates derived from exchange health."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data.normalization import normalize_timestamp
from abtp.data.quality import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain.models import JsonValue
from abtp.exchanges.reliability import DECIMAL_ONE, DECIMAL_ZERO


class TradingPermission(StrEnum):
    """Permission recommendation states for future trading workflows."""

    READ_ONLY = "read_only"
    PAPER_ONLY = "paper_only"
    BLOCK_NEW_ENTRIES = "block_new_entries"
    PAUSE_TRADING = "pause_trading"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True, slots=True)
class PermissionGatePolicy:
    """Fail-closed thresholds for exchange-health permission recommendations."""

    min_read_write_score: Decimal = Decimal("0.80")
    min_paper_score: Decimal = Decimal("0.60")
    min_manual_review_score: Decimal = Decimal("0.40")
    policy_version: str = "stage-048.permission.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("min_read_write_score", self.min_read_write_score),
            ("min_paper_score", self.min_paper_score),
            ("min_manual_review_score", self.min_manual_review_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.min_read_write_score < self.min_paper_score:
            raise ValueError("min_read_write_score must be at least min_paper_score")
        if self.min_paper_score < self.min_manual_review_score:
            raise ValueError("min_paper_score must be at least min_manual_review_score")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class PermissionGateInput:
    """Health evidence consumed by permission gate rules."""

    exchange_name: str
    checked_at: datetime
    health_score: Decimal
    health_status: str
    quality: DataQualityStatus
    rejection_reasons: tuple[str, ...] = ()
    health_reasons: tuple[str, ...] = ()
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.exchange_name.strip():
            raise ValueError("exchange_name is required")
        if not DECIMAL_ZERO <= self.health_score <= DECIMAL_ONE:
            raise ValueError("health_score must be between 0 and 1")
        object.__setattr__(self, "checked_at", normalize_timestamp(self.checked_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class PermissionGateRecommendation:
    """Advisory permission gate; it never approves risk or submits orders."""

    exchange_name: str
    checked_at: datetime
    permission: TradingPermission
    block_new_entries: bool
    pause_trading: bool
    manual_review_required: bool
    reasons: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("permission gate reasons are required")
        object.__setattr__(self, "checked_at", normalize_timestamp(self.checked_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "exchange_name": self.exchange_name,
            "checked_at": self.checked_at.isoformat(),
            "permission": self.permission.value,
            "block_new_entries": self.block_new_entries,
            "pause_trading": self.pause_trading,
            "manual_review_required": self.manual_review_required,
            "reasons": list(self.reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "exchange_name": self.exchange_name,
            "permission": self.permission.value,
            "block_new_entries": str(self.block_new_entries),
            "pause_trading": str(self.pause_trading),
            "manual_review_required": str(self.manual_review_required),
            "reasons": "|".join(self.reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject execution authority."""

        raise ValueError("exchange health permission gate cannot submit orders")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        """Reject order-intent authority."""

        raise ValueError("exchange health permission gate cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        """Reject risk-approval authority."""

        raise ValueError("exchange health permission gate cannot approve risk")


def recommend_permission_gate(
    inputs: PermissionGateInput,
    *,
    policy: PermissionGatePolicy | None = None,
) -> PermissionGateRecommendation:
    """Return the safest permission recommendation supported by health evidence."""

    active_policy = policy or PermissionGatePolicy()
    reasons = list(inputs.rejection_reasons or inputs.health_reasons)
    permission = TradingPermission.BLOCK_NEW_ENTRIES
    block_new_entries = True
    pause_trading = False
    manual_review_required = False

    if inputs.quality.is_rejected or inputs.health_status in {"unavailable", "manual_review"}:
        permission = TradingPermission.PAUSE_TRADING
        pause_trading = True
        manual_review_required = True
        reasons.append("exchange health is rejected or unavailable")
    elif inputs.health_score < active_policy.min_manual_review_score:
        permission = TradingPermission.MANUAL_REVIEW
        manual_review_required = True
        reasons.append("exchange health score requires manual review")
    elif inputs.health_score < active_policy.min_paper_score or inputs.quality.is_degraded:
        permission = TradingPermission.PAPER_ONLY
        reasons.append("exchange health supports paper-only review")
    elif inputs.health_score < active_policy.min_read_write_score:
        permission = TradingPermission.BLOCK_NEW_ENTRIES
        reasons.append("exchange health blocks new entries")
    else:
        permission = TradingPermission.READ_ONLY
        block_new_entries = False
        reasons.append("exchange health evidence permits read-only monitoring")

    quality = _gate_quality(inputs, permission)
    return PermissionGateRecommendation(
        exchange_name=inputs.exchange_name,
        checked_at=inputs.checked_at,
        permission=permission,
        block_new_entries=block_new_entries,
        pause_trading=pause_trading,
        manual_review_required=manual_review_required,
        reasons=tuple(dict.fromkeys(reasons)),
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=inputs.source_refs,
    )


def _gate_quality(
    inputs: PermissionGateInput,
    permission: TradingPermission,
) -> DataQualityStatus:
    issues = list(inputs.quality.issues)
    if permission is not TradingPermission.READ_ONLY:
        severity = (
            DataTrustLevel.REJECTED
            if permission in {TradingPermission.PAUSE_TRADING, TradingPermission.MANUAL_REVIEW}
            else DataTrustLevel.DEGRADED
        )
        issues.append(
            DataQualityIssue(
                flag=f"exchange_permission_{permission.value}",
                severity=severity,
                reason=f"exchange permission recommendation is {permission.value}",
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
        source_ref="exchange:permission_gate",
        checked_at=inputs.checked_at,
    )
