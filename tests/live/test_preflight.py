from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.domain import (
    Asset,
    AssetPair,
    OrderIntent,
    OrderSide,
    OrderType,
    RiskCheck,
    RiskDecision,
    RiskDecisionStatus,
    Signal,
    SignalDirection,
)
from abtp.live import LiveMarketPreflight, LivePreflightConfig, run_live_preflight
from abtp.security import ExchangeKeyPermissions

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_preflight_accepts_tiny_risk_approved_trading_only_order() -> None:
    result = run_live_preflight(_approved_intent(), _market(), now=NOW)

    assert result.allowed
    assert result.preview.estimated_notional == Decimal("10.0000")
    assert result.preview.max_risk_notional == Decimal("25.0000")


def test_preflight_rejects_unsafe_scopes_and_open_position_limit() -> None:
    result = run_live_preflight(
        _approved_intent(),
        _market(scopes=("read", "trade", "withdraw"), open_positions=1),
        now=NOW,
    )

    assert not result.allowed
    assert "maximum open live positions reached" in result.reasons
    assert any("withdraw" in reason for reason in result.reasons)


def test_preflight_rejects_order_without_approved_risk() -> None:
    intent = OrderIntent(
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.0001"),
        created_at=NOW,
        signal=_signal(),
    )

    result = run_live_preflight(intent, _market(), now=NOW)

    assert not result.allowed
    assert "order intent cannot bypass risk decision" in result.reasons


def test_preflight_rejects_large_notional_and_spread() -> None:
    result = run_live_preflight(
        _approved_intent(quantity=Decimal("0.001")),
        _market(spread_bps=Decimal("75")),
        now=NOW,
    )

    assert not result.allowed
    assert "order notional exceeds tiny live risk limit" in result.reasons
    assert "live spread exceeds preflight limit" in result.reasons


@pytest.mark.parametrize(
    "field,label", [("checked_at", "market snapshot"), ("account_checked_at", "account snapshot")]
)
@pytest.mark.parametrize(
    "offset,allowed,reason",
    [
        (-30, True, ""),
        (-31, False, "is stale"),
        (2, True, ""),
        (3, False, "timestamp is in the future"),
    ],
)
def test_preflight_market_and_account_freshness(
    field: str, label: str, offset: int, allowed: bool, reason: str
) -> None:
    market = replace(_market(), **{field: NOW + timedelta(seconds=offset)})
    result = run_live_preflight(_approved_intent(), market, now=NOW)
    assert result.allowed is allowed
    if not allowed:
        assert f"{label} {reason}" in result.reasons


@pytest.mark.parametrize("label", ["order intent", "risk decision"])
@pytest.mark.parametrize(
    "offset,allowed,reason",
    [
        (-300, True, ""),
        (-301, False, "is stale"),
        (2, True, ""),
        (3, False, "timestamp is in the future"),
    ],
)
def test_preflight_risk_and_intent_freshness(
    label: str, offset: int, allowed: bool, reason: str
) -> None:
    intent = _approved_intent()
    timestamp = NOW + timedelta(seconds=offset)
    if label == "order intent":
        intent = replace(intent, created_at=timestamp)
    else:
        assert intent.risk_decision is not None
        intent = replace(
            intent, risk_decision=replace(intent.risk_decision, evaluated_at=timestamp)
        )
    result = run_live_preflight(intent, _market(), now=NOW)
    assert result.allowed is allowed
    if not allowed:
        assert f"{label} {reason}" in result.reasons


def test_preflight_uses_current_clock_when_now_is_omitted() -> None:
    result = run_live_preflight(_approved_intent(), _market())
    assert not result.allowed
    assert "market snapshot is stale" in result.reasons


@pytest.mark.parametrize(
    "field", ["max_market_age", "max_account_age", "max_risk_age", "max_intent_age"]
)
def test_preflight_rejects_nonpositive_freshness_limits(field: str) -> None:
    with pytest.raises(ValueError, match="freshness limits"):
        LivePreflightConfig(**{field: timedelta(0)})


def test_preflight_rejects_negative_clock_skew() -> None:
    with pytest.raises(ValueError, match="max_clock_skew"):
        LivePreflightConfig(max_clock_skew=timedelta(seconds=-1))


def _market(
    *,
    scopes: tuple[str, ...] = ("read", "trade"),
    open_positions: int = 0,
    spread_bps: Decimal = Decimal("10"),
) -> LiveMarketPreflight:
    return LiveMarketPreflight(
        price=Decimal("100000"),
        quote_balance_available=Decimal("1000"),
        account_equity=Decimal("10000"),
        fee_bps=Decimal("20"),
        spread_bps=spread_bps,
        slippage_bps=Decimal("5"),
        open_live_positions=open_positions,
        permissions=ExchangeKeyPermissions.from_strings(
            exchange_name="fake-live",
            scopes=scopes,
            ip_allowlist=("203.0.113.10",),
        ),
        checked_at=NOW,
        account_checked_at=NOW,
    )


def _approved_intent(quantity: Decimal = Decimal("0.0001")) -> OrderIntent:
    initial = OrderIntent(
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=quantity,
        created_at=NOW,
        signal=_signal(),
    )
    decision = RiskDecision(
        order_intent_id=initial.id,
        status=RiskDecisionStatus.APPROVED,
        checks=(RiskCheck("fixture", True, "approved"),),
        evaluated_at=NOW,
        policy_version="risk-v1",
        rationale="approved",
        max_position_size=Decimal("0.001"),
    )
    return OrderIntent(
        id=initial.id,
        pair=initial.pair,
        side=initial.side,
        order_type=initial.order_type,
        quantity=initial.quantity,
        created_at=initial.created_at,
        signal=initial.signal,
        risk_decision=decision,
    )


def _signal() -> Signal:
    return Signal(
        source="fixture",
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        generated_at=NOW,
        direction=SignalDirection.BUY,
        confidence=Decimal("0.75"),
        inputs_ref="fixture:features",
        rationale="fixture",
    )
