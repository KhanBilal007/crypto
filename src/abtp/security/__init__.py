"""Security hardening exports."""

from abtp.security.auth import (
    AuthenticatedPrincipal,
    SecurityPermission,
    SecurityRole,
    assert_can_read_audit,
)
from abtp.security.dependencies import (
    DependencyAuditNote,
    DependencyAuditReport,
    DependencyRiskLevel,
    build_dependency_audit_report,
)
from abtp.security.permissions import (
    ExchangeAPIScope,
    ExchangeKeyPermissions,
    ExchangeKeyPolicy,
    PermissionValidationResult,
    validate_exchange_key_permissions,
)
from abtp.security.secrets import (
    EncryptedSecretRef,
    SecretFingerprint,
    assert_no_plaintext_secret_keys,
    is_secret_key,
    mask_secret,
)

__all__ = [
    "AuthenticatedPrincipal",
    "DependencyAuditNote",
    "DependencyAuditReport",
    "DependencyRiskLevel",
    "EncryptedSecretRef",
    "ExchangeAPIScope",
    "ExchangeKeyPermissions",
    "ExchangeKeyPolicy",
    "PermissionValidationResult",
    "SecretFingerprint",
    "SecurityPermission",
    "SecurityRole",
    "assert_can_read_audit",
    "assert_no_plaintext_secret_keys",
    "build_dependency_audit_report",
    "is_secret_key",
    "mask_secret",
    "validate_exchange_key_permissions",
]
