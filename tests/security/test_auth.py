from __future__ import annotations

import pytest

from abtp.security import (
    AuthenticatedPrincipal,
    SecurityPermission,
    SecurityRole,
    assert_can_read_audit,
)


def test_auditor_can_read_audit_but_not_manage_security() -> None:
    principal = AuthenticatedPrincipal("auditor-1", frozenset({SecurityRole.AUDITOR}))

    assert_can_read_audit(principal)
    assert principal.has_permission(SecurityPermission.READ_AUDIT)
    assert not principal.has_permission(SecurityPermission.MANAGE_SECURITY)


def test_viewer_cannot_read_audit_or_control_paper() -> None:
    principal = AuthenticatedPrincipal("viewer-1", frozenset({SecurityRole.VIEWER}))

    with pytest.raises(PermissionError, match="read_audit"):
        assert_can_read_audit(principal)
    with pytest.raises(PermissionError, match="control_paper"):
        principal.require(SecurityPermission.CONTROL_PAPER)


def test_admin_has_all_permissions() -> None:
    principal = AuthenticatedPrincipal("admin-1", frozenset({SecurityRole.ADMIN}))

    assert all(principal.has_permission(permission) for permission in SecurityPermission)
