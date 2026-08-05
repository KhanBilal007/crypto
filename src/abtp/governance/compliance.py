"""Operational governance and compliance reporting."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue


class ApprovalSubjectType(StrEnum):
    """Governed subject types."""

    STRATEGY = "strategy"
    MODEL = "model"
    CONFIGURATION = "configuration"
    MANUAL_OVERRIDE = "manual_override"


class ApprovalStatus(StrEnum):
    """Approval workflow states."""

    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"


class PolicyViolationType(StrEnum):
    """Governance policy violation categories."""

    MISSING_STRATEGY_APPROVAL = "missing_strategy_approval"
    MISSING_MODEL_APPROVAL = "missing_model_approval"
    MISSING_CONFIG_VERSION = "missing_config_version"
    UNAPPROVED_CONFIG_VERSION = "unapproved_config_version"
    UNLOGGED_MANUAL_OVERRIDE = "unlogged_manual_override"
    REJECTED_OR_REVOKED_APPROVAL = "rejected_or_revoked_approval"
    REJECTED_QUALITY = "rejected_quality"


class ComplianceStatus(StrEnum):
    """Compliance report status."""

    COMPLIANT = "compliant"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class GovernancePolicy:
    """Conservative Stage 068 governance policy."""

    require_strategy_approval: bool = True
    require_model_approval: bool = True
    require_config_versioning: bool = True
    require_manual_override_log: bool = True
    require_config_approval: bool = True
    policy_version: str = "stage-068.v1"

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class GovernanceApprovalRecord:
    """One strategy, model, config, or override approval workflow record."""

    approval_id: str
    subject_type: ApprovalSubjectType
    subject_id: str
    status: ApprovalStatus
    requested_by: str
    requested_at: datetime
    rationale: str
    decided_by: str | None = None
    decided_at: datetime | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject_type", ApprovalSubjectType(self.subject_type))
        object.__setattr__(self, "status", ApprovalStatus(self.status))
        for value, field_name in (
            (self.approval_id, "approval_id"),
            (self.subject_id, "subject_id"),
            (self.requested_by, "requested_by"),
            (self.rationale, "approval rationale"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")
        if self.status in {
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
            ApprovalStatus.REVOKED,
        }:
            if not self.decided_by or not self.decided_by.strip():
                raise ValueError("decided_by is required for decided approvals")
            if self.decided_at is None:
                raise ValueError("decided_at is required for decided approvals")
        object.__setattr__(self, "requested_at", normalize_timestamp(self.requested_at))
        if self.decided_at is not None:
            object.__setattr__(self, "decided_at", normalize_timestamp(self.decided_at))
            if self.decided_at < self.requested_at:
                raise ValueError("decided_at cannot be before requested_at")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))

    @property
    def approved(self) -> bool:
        return self.status is ApprovalStatus.APPROVED

    def as_dict(self) -> dict[str, object]:
        return {
            "approval_id": self.approval_id,
            "subject_type": self.subject_type.value,
            "subject_id": self.subject_id,
            "status": self.status.value,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at.isoformat(),
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "rationale": self.rationale,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class ConfigVersionRecord:
    """Versioned configuration record without secret values."""

    config_key: str
    version: str
    checksum: str
    created_by: str
    created_at: datetime
    approval_id: str | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.config_key, "config_key"),
            (self.version, "version"),
            (self.checksum, "checksum"),
            (self.created_by, "created_by"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")
        secret_terms = ("secret", "password", "token", "private_key")
        if any(term in self.config_key.lower() for term in secret_terms):
            raise ValueError("configuration records must not identify secret values")
        object.__setattr__(self, "created_at", normalize_timestamp(self.created_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "config_key": self.config_key,
            "version": self.version,
            "checksum": self.checksum,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "approval_id": self.approval_id,
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class ManualOverrideLog:
    """Audit-ready manual override log."""

    override_id: str
    scope: str
    operator_id: str
    reason: str
    occurred_at: datetime
    approval_id: str | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.override_id, "override_id"),
            (self.scope, "override scope"),
            (self.operator_id, "operator_id"),
            (self.reason, "override reason"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")
        object.__setattr__(self, "occurred_at", normalize_timestamp(self.occurred_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "override_id": self.override_id,
            "scope": self.scope,
            "operator_id": self.operator_id,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
            "approval_id": self.approval_id,
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class PolicyViolation:
    """One compliance policy violation."""

    violation_type: PolicyViolationType
    severity: DataTrustLevel
    message: str
    subject_id: str
    evidence_ref: str
    blocking: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_type", PolicyViolationType(self.violation_type))
        object.__setattr__(self, "severity", DataTrustLevel(self.severity))
        for value, field_name in (
            (self.message, "violation message"),
            (self.subject_id, "violation subject_id"),
            (self.evidence_ref, "violation evidence_ref"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "violation_type": self.violation_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "subject_id": self.subject_id,
            "evidence_ref": self.evidence_ref,
            "blocking": self.blocking,
        }


@dataclass(frozen=True, slots=True)
class GovernanceReviewInput:
    """Evidence for one governance/compliance review."""

    generated_at: datetime
    approvals: Sequence[GovernanceApprovalRecord]
    config_versions: Sequence[ConfigVersionRecord] = ()
    manual_overrides: Sequence[ManualOverrideLog] = ()
    required_strategy_ids: tuple[str, ...] = ()
    required_model_ids: tuple[str, ...] = ()
    active_config_keys: tuple[str, ...] = ()
    pending_manual_override_ids: tuple[str, ...] = ()
    quality: DataQualityStatus | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "approvals", tuple(self.approvals))
        object.__setattr__(self, "config_versions", tuple(self.config_versions))
        object.__setattr__(self, "manual_overrides", tuple(self.manual_overrides))
        object.__setattr__(
            self, "required_strategy_ids", tuple(_normalized_texts(self.required_strategy_ids))
        )
        object.__setattr__(
            self, "required_model_ids", tuple(_normalized_texts(self.required_model_ids))
        )
        object.__setattr__(
            self, "active_config_keys", tuple(_normalized_texts(self.active_config_keys))
        )
        object.__setattr__(
            self,
            "pending_manual_override_ids",
            tuple(_normalized_texts(self.pending_manual_override_ids)),
        )
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def review_quality(self) -> DataQualityStatus:
        return self.quality or DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref="governance:review_input",
            checked_at=self.generated_at,
        )


@dataclass(frozen=True, slots=True)
class GovernanceReviewReport:
    """Audit-ready compliance report."""

    generated_at: datetime
    compliance_status: ComplianceStatus
    approval_history: tuple[GovernanceApprovalRecord, ...]
    config_versions: tuple[ConfigVersionRecord, ...]
    manual_overrides: tuple[ManualOverrideLog, ...]
    policy_violations: tuple[PolicyViolation, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Governance reports are advisory compliance context only.",
        "Governance cannot create signals, approve risk, create order intents, or execute trades.",
        "Approval records do not bypass the Risk Management Engine.",
        "Configuration records must not contain plaintext secrets.",
        "No profit is guaranteed by governance compliance reporting.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "compliance_status", ComplianceStatus(self.compliance_status))
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("governance report limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def compliant(self) -> bool:
        return self.compliance_status is ComplianceStatus.COMPLIANT and self.quality.is_trusted

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("governance report cannot create signals")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("governance report cannot approve risk")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("governance report cannot create order intents")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("governance report cannot submit orders")

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "compliance_status": self.compliance_status.value,
            "approval_history": [item.as_dict() for item in self.approval_history],
            "config_versions": [item.as_dict() for item in self.config_versions],
            "manual_overrides": [item.as_dict() for item in self.manual_overrides],
            "policy_violations": [item.as_dict() for item in self.policy_violations],
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "compliance_status": self.compliance_status.value,
            "approval_count": len(self.approval_history),
            "config_version_count": len(self.config_versions),
            "manual_override_count": len(self.manual_overrides),
            "policy_violation_count": len(self.policy_violations),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }


def build_governance_review_report(
    review_input: GovernanceReviewInput,
    *,
    policy: GovernancePolicy | None = None,
) -> GovernanceReviewReport:
    """Build a deterministic governance and compliance report."""

    active_policy = policy or GovernancePolicy()
    violations = _violations(review_input, active_policy)
    quality = _quality(review_input, violations, active_policy)
    status = _compliance_status(violations, quality)
    return GovernanceReviewReport(
        generated_at=review_input.generated_at,
        compliance_status=status,
        approval_history=tuple(sorted(review_input.approvals, key=lambda item: item.requested_at)),
        config_versions=tuple(
            sorted(review_input.config_versions, key=lambda item: item.created_at)
        ),
        manual_overrides=tuple(
            sorted(review_input.manual_overrides, key=lambda item: item.occurred_at)
        ),
        policy_violations=violations,
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=review_input.source_refs,
    )


def _violations(
    review_input: GovernanceReviewInput,
    policy: GovernancePolicy,
) -> tuple[PolicyViolation, ...]:
    violations: list[PolicyViolation] = []
    approval_lookup = {
        (approval.subject_type, approval.subject_id): approval
        for approval in review_input.approvals
    }
    if policy.require_strategy_approval:
        for strategy_id in review_input.required_strategy_ids:
            approval = approval_lookup.get((ApprovalSubjectType.STRATEGY, strategy_id))
            if approval is None or not approval.approved:
                violations.append(
                    _violation(
                        PolicyViolationType.MISSING_STRATEGY_APPROVAL,
                        strategy_id,
                        "strategy approval is missing or not approved",
                    )
                )
    if policy.require_model_approval:
        for model_id in review_input.required_model_ids:
            approval = approval_lookup.get((ApprovalSubjectType.MODEL, model_id))
            if approval is None or not approval.approved:
                violations.append(
                    _violation(
                        PolicyViolationType.MISSING_MODEL_APPROVAL,
                        model_id,
                        "model approval is missing or not approved",
                    )
                )
    if policy.require_config_versioning:
        config_lookup = {item.config_key: item for item in review_input.config_versions}
        for config_key in review_input.active_config_keys:
            record = config_lookup.get(config_key)
            if record is None:
                violations.append(
                    _violation(
                        PolicyViolationType.MISSING_CONFIG_VERSION,
                        config_key,
                        "active configuration key is not versioned",
                    )
                )
            elif policy.require_config_approval and not _config_is_approved(record, review_input):
                violations.append(
                    _violation(
                        PolicyViolationType.UNAPPROVED_CONFIG_VERSION,
                        config_key,
                        "configuration version lacks approved change record",
                    )
                )
    if policy.require_manual_override_log:
        logged_overrides = {item.override_id for item in review_input.manual_overrides}
        for override_id in review_input.pending_manual_override_ids:
            if override_id not in logged_overrides:
                violations.append(
                    _violation(
                        PolicyViolationType.UNLOGGED_MANUAL_OVERRIDE,
                        override_id,
                        "manual override is not logged",
                    )
                )
    for approval in review_input.approvals:
        if approval.status in {ApprovalStatus.REJECTED, ApprovalStatus.REVOKED}:
            violations.append(
                _violation(
                    PolicyViolationType.REJECTED_OR_REVOKED_APPROVAL,
                    approval.subject_id,
                    f"{approval.subject_type.value} approval is {approval.status.value}",
                    evidence_ref=approval.approval_id,
                )
            )
    if review_input.review_quality.is_rejected:
        violations.append(
            _violation(
                PolicyViolationType.REJECTED_QUALITY,
                "governance_review_input",
                "governance review input quality is rejected",
            )
        )
    return tuple(violations)


def _config_is_approved(
    record: ConfigVersionRecord,
    review_input: GovernanceReviewInput,
) -> bool:
    if not record.approval_id:
        return False
    return any(
        approval.approval_id == record.approval_id
        and approval.subject_type is ApprovalSubjectType.CONFIGURATION
        and approval.approved
        for approval in review_input.approvals
    )


def _quality(
    review_input: GovernanceReviewInput,
    violations: Sequence[PolicyViolation],
    policy: GovernancePolicy,
) -> DataQualityStatus:
    issues = list(review_input.review_quality.issues)
    for violation in violations:
        issues.append(
            DataQualityIssue(
                flag=f"governance_{violation.violation_type.value}",
                severity=violation.severity,
                reason=violation.message,
            )
        )
    if not review_input.approvals and (
        policy.require_model_approval or policy.require_strategy_approval
    ):
        issues.append(
            DataQualityIssue(
                flag="missing_approval_history",
                severity=DataTrustLevel.REJECTED,
                reason="approval history is required for governance review",
            )
        )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif any(issue.severity is DataTrustLevel.DEGRADED for issue in issues):
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="governance:compliance_report",
        checked_at=review_input.generated_at,
    )


def _compliance_status(
    violations: Sequence[PolicyViolation],
    quality: DataQualityStatus,
) -> ComplianceStatus:
    if quality.is_rejected or any(violation.blocking for violation in violations):
        return ComplianceStatus.BLOCKED
    if violations or quality.is_degraded:
        return ComplianceStatus.REVIEW_REQUIRED
    return ComplianceStatus.COMPLIANT


def _violation(
    violation_type: PolicyViolationType,
    subject_id: str,
    message: str,
    *,
    evidence_ref: str | None = None,
) -> PolicyViolation:
    return PolicyViolation(
        violation_type=violation_type,
        severity=DataTrustLevel.REJECTED,
        message=message,
        subject_id=subject_id,
        evidence_ref=evidence_ref or f"governance:{violation_type.value}:{subject_id}",
        blocking=True,
    )


def _normalized_texts(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value.strip() for value in values if value.strip())
