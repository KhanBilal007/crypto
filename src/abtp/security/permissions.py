"""Least-privilege exchange API permission validation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class ExchangeAPIScope(StrEnum):
    """Exchange API scopes known to Stage 031 validation."""

    READ = "read"
    TRADE = "trade"
    WITHDRAW = "withdraw"
    TRANSFER = "transfer"
    MARGIN = "margin"
    FUTURES = "futures"
    OPTIONS = "options"
    ADMIN = "admin"


UNSAFE_EXCHANGE_SCOPES = frozenset(
    {
        ExchangeAPIScope.WITHDRAW,
        ExchangeAPIScope.TRANSFER,
        ExchangeAPIScope.MARGIN,
        ExchangeAPIScope.FUTURES,
        ExchangeAPIScope.OPTIONS,
        ExchangeAPIScope.ADMIN,
    }
)


@dataclass(frozen=True, slots=True)
class ExchangeKeyPermissions:
    """Declared exchange-key capabilities without secret values."""

    exchange_name: str
    scopes: frozenset[ExchangeAPIScope]
    ip_allowlist: tuple[str, ...] = ()
    trading_only: bool = True

    def __post_init__(self) -> None:
        if not self.exchange_name.strip():
            raise ValueError("exchange_name is required")
        if not self.scopes:
            raise ValueError("exchange key scopes are required")
        if any(not item.strip() for item in self.ip_allowlist):
            raise ValueError("ip_allowlist entries cannot be blank")

    @classmethod
    def from_strings(
        cls,
        *,
        exchange_name: str,
        scopes: Iterable[str],
        ip_allowlist: Iterable[str] = (),
    ) -> ExchangeKeyPermissions:
        return cls(
            exchange_name=exchange_name,
            scopes=frozenset(ExchangeAPIScope(item.strip().lower()) for item in scopes),
            ip_allowlist=tuple(item.strip() for item in ip_allowlist if item.strip()),
        )

    @property
    def unsafe_scopes(self) -> frozenset[ExchangeAPIScope]:
        return self.scopes & UNSAFE_EXCHANGE_SCOPES


@dataclass(frozen=True, slots=True)
class ExchangeKeyPolicy:
    """Least-privilege exchange key policy."""

    require_read: bool = True
    require_trade: bool = True
    require_ip_allowlist: bool = True
    allow_withdrawals: bool = False


@dataclass(frozen=True, slots=True)
class PermissionValidationResult:
    """Exchange permission validation result."""

    allowed: bool
    reasons: tuple[str, ...]

    def require_allowed(self) -> None:
        if not self.allowed:
            raise PermissionError("; ".join(self.reasons))


def validate_exchange_key_permissions(
    permissions: ExchangeKeyPermissions,
    *,
    policy: ExchangeKeyPolicy | None = None,
) -> PermissionValidationResult:
    """Validate that exchange keys are least-privilege and withdrawal-free."""

    active_policy = policy or ExchangeKeyPolicy()
    reasons: list[str] = []
    if active_policy.require_read and ExchangeAPIScope.READ not in permissions.scopes:
        reasons.append("exchange key requires read scope")
    if active_policy.require_trade and ExchangeAPIScope.TRADE not in permissions.scopes:
        reasons.append("exchange key requires trade scope")
    unsafe_scopes = permissions.unsafe_scopes
    if unsafe_scopes:
        reasons.append(
            "unsupported exchange key scopes: "
            + ",".join(sorted(scope.value for scope in unsafe_scopes))
        )
    if active_policy.require_ip_allowlist and not permissions.ip_allowlist:
        reasons.append("exchange key requires IP allowlist")
    if not permissions.trading_only:
        reasons.append("exchange key must be trading-only")
    return PermissionValidationResult(allowed=not reasons, reasons=tuple(reasons))
