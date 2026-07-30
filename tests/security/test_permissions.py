from __future__ import annotations

import pytest

from abtp.security import (
    ExchangeAPIScope,
    ExchangeKeyPermissions,
    ExchangeKeyPolicy,
    validate_exchange_key_permissions,
)


def test_trading_only_key_with_ip_allowlist_is_allowed() -> None:
    permissions = ExchangeKeyPermissions(
        exchange_name="coinbase",
        scopes=frozenset({ExchangeAPIScope.READ, ExchangeAPIScope.TRADE}),
        ip_allowlist=("203.0.113.10",),
    )

    result = validate_exchange_key_permissions(permissions)

    assert result.allowed
    assert result.reasons == ()


def test_withdrawal_scope_is_rejected_even_with_trade_scope() -> None:
    permissions = ExchangeKeyPermissions.from_strings(
        exchange_name="kraken",
        scopes=("read", "trade", "withdraw"),
        ip_allowlist=("203.0.113.10",),
    )

    result = validate_exchange_key_permissions(permissions)

    assert not result.allowed
    assert "withdraw" in result.reasons[0]
    with pytest.raises(PermissionError, match="withdraw"):
        result.require_allowed()


def test_missing_ip_allowlist_and_trade_scope_fail_closed() -> None:
    permissions = ExchangeKeyPermissions(
        exchange_name="coinbase",
        scopes=frozenset({ExchangeAPIScope.READ}),
    )

    result = validate_exchange_key_permissions(permissions)

    assert not result.allowed
    assert "exchange key requires trade scope" in result.reasons
    assert "exchange key requires IP allowlist" in result.reasons


def test_policy_cannot_allow_unsupported_margin_or_futures_scopes() -> None:
    permissions = ExchangeKeyPermissions(
        exchange_name="fixture",
        scopes=frozenset({ExchangeAPIScope.READ, ExchangeAPIScope.TRADE, ExchangeAPIScope.FUTURES}),
        ip_allowlist=("203.0.113.10",),
    )

    result = validate_exchange_key_permissions(
        permissions,
        policy=ExchangeKeyPolicy(allow_withdrawals=True),
    )

    assert not result.allowed
    assert "futures" in result.reasons[0]
