"""Authentication and authorization contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SecurityRole(StrEnum):
    """Operator roles for Stage 031 authorization."""

    VIEWER = "viewer"
    OPERATOR = "operator"
    RISK_MANAGER = "risk_manager"
    AUDITOR = "auditor"
    ADMIN = "admin"


class SecurityPermission(StrEnum):
    """Fine-grained permissions used by APIs and future adapters."""

    READ_PAPER_STATE = "read_paper_state"
    CONTROL_PAPER = "control_paper"
    READ_AUDIT = "read_audit"
    MANAGE_RISK = "manage_risk"
    MANAGE_SECURITY = "manage_security"


ROLE_PERMISSIONS: dict[SecurityRole, frozenset[SecurityPermission]] = {
    SecurityRole.VIEWER: frozenset({SecurityPermission.READ_PAPER_STATE}),
    SecurityRole.OPERATOR: frozenset(
        {SecurityPermission.READ_PAPER_STATE, SecurityPermission.CONTROL_PAPER}
    ),
    SecurityRole.RISK_MANAGER: frozenset(
        {
            SecurityPermission.READ_PAPER_STATE,
            SecurityPermission.CONTROL_PAPER,
            SecurityPermission.MANAGE_RISK,
        }
    ),
    SecurityRole.AUDITOR: frozenset(
        {SecurityPermission.READ_PAPER_STATE, SecurityPermission.READ_AUDIT}
    ),
    SecurityRole.ADMIN: frozenset(SecurityPermission),
}


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Authenticated user/service identity without credentials."""

    principal_id: str
    roles: frozenset[SecurityRole]

    def __post_init__(self) -> None:
        if not self.principal_id.strip():
            raise ValueError("principal_id is required")
        if not self.roles:
            raise ValueError("at least one role is required")

    @property
    def permissions(self) -> frozenset[SecurityPermission]:
        merged: set[SecurityPermission] = set()
        for role in self.roles:
            merged.update(ROLE_PERMISSIONS[role])
        return frozenset(merged)

    def has_permission(self, permission: SecurityPermission) -> bool:
        return permission in self.permissions

    def require(self, permission: SecurityPermission) -> None:
        if not self.has_permission(permission):
            raise PermissionError(f"missing permission: {permission.value}")


def assert_can_read_audit(principal: AuthenticatedPrincipal) -> None:
    """Require audit-read permission for audit trail access."""

    principal.require(SecurityPermission.READ_AUDIT)
