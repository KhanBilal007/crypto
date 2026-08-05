from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

import abtp


def test_project_imports() -> None:
    assert abtp.RuntimeSettings().safe_mode is True


def test_live_execution_is_impossible_in_stage_005(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAFE_MODE", "false")
    monkeypatch.setenv("ABTP_TRADING_MODE", "live")
    monkeypatch.setenv("ABTP_ENABLE_LIVE_TRADING", "true")

    settings = abtp.RuntimeSettings.from_env()

    assert settings.live_execution_supported is False
    assert settings.can_execute_live is False


def test_order_intent_requires_matching_risk_decision() -> None:
    btc = abtp.Asset("btc", "Bitcoin")
    usdt = abtp.Asset("usdt", "Tether USD")
    pair = abtp.TradingPair(btc, usdt)
    exchange = abtp.Exchange("fixture-exchange")
    opened_at = datetime(2026, 1, 1, tzinfo=UTC)
    closed_at = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    candle = abtp.Candle(
        exchange=exchange,
        pair=pair,
        interval="1m",
        opened_at=opened_at,
        closed_at=closed_at,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("2"),
    )
    signal = abtp.Signal(
        source="fixture-strategy",
        pair=candle.pair,
        generated_at=closed_at,
        direction=abtp.SignalDirection.HOLD,
        confidence=Decimal("0.75"),
        inputs_ref="fixture:candle:btc-usdt-2026-01-01T00:01Z",
        rationale="Fixture signal for deterministic contract validation.",
    )
    intent = abtp.OrderIntent(
        pair=pair,
        side=abtp.OrderSide.BUY,
        order_type=abtp.OrderType.MARKET,
        quantity=Decimal("0.01"),
        created_at=closed_at,
        signal=signal,
    )
    risk_decision = abtp.RiskDecision(
        order_intent_id=intent.id,
        status=abtp.RiskDecisionStatus.APPROVED,
        checks=(abtp.RiskCheck("fixture-check", True, "deterministic pass"),),
        evaluated_at=closed_at,
        policy_version="stage-005",
        rationale="All fixture checks passed.",
    )
    approved_intent = abtp.OrderIntent(
        id=intent.id,
        pair=intent.pair,
        side=intent.side,
        order_type=intent.order_type,
        quantity=intent.quantity,
        created_at=intent.created_at,
        signal=intent.signal,
        risk_decision=risk_decision,
    )

    assert approved_intent.risk_decision == risk_decision
