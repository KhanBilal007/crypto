from __future__ import annotations

import pytest

from abtp.security import (
    DependencyAuditNote,
    DependencyRiskLevel,
    build_dependency_audit_report,
)


def test_dependency_audit_report_orders_notes_and_flags_review() -> None:
    report = build_dependency_audit_report(
        (
            DependencyAuditNote("ruff", "0.5", DependencyRiskLevel.OK, "dev lint tool"),
            DependencyAuditNote("pytest", "8", DependencyRiskLevel.REVIEW, "review new major"),
        )
    )

    assert not report.blocked
    assert report.requires_review
    assert report.as_dict()["notes"][0]["package"] == "pytest"  # type: ignore[index]


def test_blocked_dependency_report_fails_closed() -> None:
    report = build_dependency_audit_report(
        (
            DependencyAuditNote(
                "unsafe-package",
                "1.0",
                DependencyRiskLevel.BLOCKED,
                "known local fixture finding",
            ),
        )
    )

    with pytest.raises(RuntimeError, match="unsafe-package"):
        report.require_not_blocked()
