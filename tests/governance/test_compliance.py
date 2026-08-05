from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.governance import (
    ApprovalStatus,
    ApprovalSubjectType,
    ComplianceStatus,
    ConfigVersionRecord,
    GovernanceApprovalRecord,
    GovernanceReviewInput,
    GovernanceReviewReport,
    ManualOverrideLog,
    PolicyViolationType,
    build_governance_review_report,
)

NOW = datetime(2026, 2, 15, tzinfo=UTC)


def test_governance_report_is_compliant_with_approved_strategy_model_and_config() -> None:
    report = build_governance_review_report(_review_input())

    assert isinstance(report, GovernanceReviewReport)
    assert report.advisory_only is True
    assert report.compliance_status is ComplianceStatus.COMPLIANT
    assert report.compliant is True
    assert report.policy_violations == ()
    assert [approval.approval_id for approval in report.approval_history] == [
        "approval-strategy",
        "approval-model",
        "approval-config",
        "approval-override",
    ]
    assert report.audit_payload()["compliance_status"] == "compliant"


def test_missing_strategy_or_model_approval_blocks_compliance() -> None:
    report = build_governance_review_report(
        GovernanceReviewInput(
            generated_at=NOW,
            approvals=(
                _approval("approval-config", ApprovalSubjectType.CONFIGURATION, "risk.yml"),
            ),
            config_versions=(_config("risk.yml", approval_id="approval-config"),),
            required_strategy_ids=("min-risk-spot-v1",),
            required_model_ids=("baseline-v1",),
            active_config_keys=("risk.yml",),
        )
    )

    violation_types = {violation.violation_type for violation in report.policy_violations}

    assert report.compliance_status is ComplianceStatus.BLOCKED
    assert PolicyViolationType.MISSING_STRATEGY_APPROVAL in violation_types
    assert PolicyViolationType.MISSING_MODEL_APPROVAL in violation_types
    assert report.quality.is_rejected


def test_unversioned_or_unapproved_config_blocks_compliance() -> None:
    report = build_governance_review_report(
        GovernanceReviewInput(
            generated_at=NOW,
            approvals=(
                _approval("approval-strategy", ApprovalSubjectType.STRATEGY, "min-risk-spot-v1"),
                _approval("approval-model", ApprovalSubjectType.MODEL, "baseline-v1"),
            ),
            config_versions=(_config("risk.yml"),),
            required_strategy_ids=("min-risk-spot-v1",),
            required_model_ids=("baseline-v1",),
            active_config_keys=("risk.yml", "live.yml"),
        )
    )

    assert report.compliance_status is ComplianceStatus.BLOCKED
    assert {
        PolicyViolationType.UNAPPROVED_CONFIG_VERSION,
        PolicyViolationType.MISSING_CONFIG_VERSION,
    } <= {violation.violation_type for violation in report.policy_violations}


def test_manual_override_must_be_logged() -> None:
    report = build_governance_review_report(
        GovernanceReviewInput(
            generated_at=NOW,
            approvals=_approvals(),
            config_versions=(_config("risk.yml", approval_id="approval-config"),),
            manual_overrides=(),
            required_strategy_ids=("min-risk-spot-v1",),
            required_model_ids=("baseline-v1",),
            active_config_keys=("risk.yml",),
            pending_manual_override_ids=("override-1",),
        )
    )

    assert report.compliance_status is ComplianceStatus.BLOCKED
    assert PolicyViolationType.UNLOGGED_MANUAL_OVERRIDE in {
        violation.violation_type for violation in report.policy_violations
    }


def test_rejected_or_revoked_approval_blocks_compliance() -> None:
    report = build_governance_review_report(
        GovernanceReviewInput(
            generated_at=NOW,
            approvals=(
                _approval(
                    "approval-strategy",
                    ApprovalSubjectType.STRATEGY,
                    "min-risk-spot-v1",
                    status=ApprovalStatus.REVOKED,
                ),
                _approval("approval-model", ApprovalSubjectType.MODEL, "baseline-v1"),
                _approval("approval-config", ApprovalSubjectType.CONFIGURATION, "risk.yml"),
            ),
            config_versions=(_config("risk.yml", approval_id="approval-config"),),
            required_strategy_ids=("min-risk-spot-v1",),
            required_model_ids=("baseline-v1",),
            active_config_keys=("risk.yml",),
        )
    )

    assert report.compliance_status is ComplianceStatus.BLOCKED
    assert PolicyViolationType.REJECTED_OR_REVOKED_APPROVAL in {
        violation.violation_type for violation in report.policy_violations
    }


def test_rejected_quality_blocks_and_config_secret_keys_are_rejected() -> None:
    report = build_governance_review_report(_review_input(quality=_rejected_quality()))

    assert report.compliance_status is ComplianceStatus.BLOCKED
    assert PolicyViolationType.REJECTED_QUALITY in {
        violation.violation_type for violation in report.policy_violations
    }
    with pytest.raises(ValueError, match="must not identify secret"):
        _config("exchange_secret_token")


def test_governance_report_has_no_signal_risk_or_order_authority() -> None:
    report = build_governance_review_report(_review_input())

    with pytest.raises(ValueError, match="cannot create signals"):
        report.create_signal()
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk()
    with pytest.raises(ValueError, match="cannot create order intents"):
        report.create_order_intent()
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()


def test_governance_public_imports_and_validation() -> None:
    assert GovernanceReviewReport.__name__ == "GovernanceReviewReport"
    with pytest.raises(ValueError, match="decided_by is required"):
        GovernanceApprovalRecord(
            approval_id="bad-approval",
            subject_type=ApprovalSubjectType.STRATEGY,
            subject_id="strategy",
            status=ApprovalStatus.APPROVED,
            requested_by="operator",
            requested_at=NOW,
            rationale="bad fixture",
        )


def _review_input(quality: DataQualityStatus | None = None) -> GovernanceReviewInput:
    return GovernanceReviewInput(
        generated_at=NOW,
        approvals=_approvals(),
        config_versions=(_config("risk.yml", approval_id="approval-config"),),
        manual_overrides=(
            ManualOverrideLog(
                override_id="override-1",
                scope="paper_pause",
                operator_id="operator-1",
                reason="fixture manual override",
                occurred_at=NOW,
                approval_id="approval-override",
            ),
        ),
        required_strategy_ids=("min-risk-spot-v1",),
        required_model_ids=("baseline-v1",),
        active_config_keys=("risk.yml",),
        pending_manual_override_ids=("override-1",),
        quality=quality,
        source_refs={"governance": "fixture:stage068"},
    )


def _approvals() -> tuple[GovernanceApprovalRecord, ...]:
    return (
        _approval("approval-strategy", ApprovalSubjectType.STRATEGY, "min-risk-spot-v1"),
        _approval("approval-model", ApprovalSubjectType.MODEL, "baseline-v1"),
        _approval("approval-config", ApprovalSubjectType.CONFIGURATION, "risk.yml"),
        _approval("approval-override", ApprovalSubjectType.MANUAL_OVERRIDE, "override-1"),
    )


def _approval(
    approval_id: str,
    subject_type: ApprovalSubjectType,
    subject_id: str,
    *,
    status: ApprovalStatus = ApprovalStatus.APPROVED,
) -> GovernanceApprovalRecord:
    return GovernanceApprovalRecord(
        approval_id=approval_id,
        subject_type=subject_type,
        subject_id=subject_id,
        status=status,
        requested_by="operator-1",
        requested_at=NOW - timedelta(hours=1),
        decided_by="risk-manager-1",
        decided_at=NOW,
        rationale=f"{subject_id} fixture approval",
        evidence_refs=(f"fixture:{subject_id}",),
    )


def _config(config_key: str, *, approval_id: str | None = None) -> ConfigVersionRecord:
    return ConfigVersionRecord(
        config_key=config_key,
        version="v1",
        checksum="sha256:fixture",
        created_by="operator-1",
        created_at=NOW,
        approval_id=approval_id,
        source_refs={config_key: f"fixture:{config_key}"},
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_governance_input",
                severity=DataTrustLevel.REJECTED,
                reason="fixture rejected governance input",
            ),
        ),
        source_ref="fixture:rejected",
        checked_at=NOW,
    )
