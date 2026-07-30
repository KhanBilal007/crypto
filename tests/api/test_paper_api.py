from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.api import (
    PaperAPIRequestContext,
    PaperAPIRole,
    PaperPermissionError,
    PaperTradingAPI,
    UnsafePaperActionError,
)
from abtp.data import OrderBookMetrics, StreamHealth
from abtp.domain import Asset, AssetPair, Candle, Exchange
from abtp.paper import PaperMarketSnapshot, PaperTradingConfig, PaperTradingEngine
from abtp.strategies import MinRiskSpotStrategyV1

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PAIR = AssetPair(Asset("BTC"), Asset("USDT"))
READ_CONTEXT = PaperAPIRequestContext("viewer", frozenset({PaperAPIRole.READ}))
CONTROL_CONTEXT = PaperAPIRequestContext(
    "operator", frozenset({PaperAPIRole.READ, PaperAPIRole.CONTROL})
)


def test_paper_status_exposes_trade_decision_context() -> None:
    engine = _engine_with_cycles(("100", "101", "102", "104"))
    api = PaperTradingAPI(engine)

    status = api.status(READ_CONTEXT)

    assert status.current_btc_price == Decimal("104")
    assert status.active_regime == "trend_up"
    assert status.latest_signal == "buy"
    assert status.latest_risk_decision == "approved"
    assert status.blocked_reason == "not blocked"
    assert status.data_health == "healthy"
    assert status.trades_count >= 1
    assert status.parameter_health
    assert status.as_dict()["portfolio"]["equity"] == str(status.portfolio.equity)  # type: ignore[index]


def test_hold_cycle_exposes_blocked_trade_reason() -> None:
    engine = _engine_with_cycles(("100",))
    api = PaperTradingAPI(engine)

    status = api.status(READ_CONTEXT)

    assert status.latest_signal == "hold"
    assert "trend confirmation is below threshold" in status.blocked_reason


def test_read_authorization_is_required_for_status() -> None:
    api = PaperTradingAPI(_engine_with_cycles(("100",)))
    no_roles = PaperAPIRequestContext("anonymous", frozenset())

    with pytest.raises(PaperPermissionError, match="paper:read"):
        api.status(no_roles)


def test_control_authorization_and_kill_switch_state() -> None:
    api = PaperTradingAPI(_engine_with_cycles(("100", "101", "102", "104")))

    with pytest.raises(PaperPermissionError, match="paper:control"):
        api.pause(READ_CONTEXT, reason="operator pause", updated_at=NOW)

    state = api.activate_kill_switch(
        CONTROL_CONTEXT,
        reason="manual safety stop",
        updated_at=NOW + timedelta(minutes=5),
    )
    status = api.status(READ_CONTEXT)

    assert state.kill_switch_active
    assert state.paused
    assert status.kill_switch_active
    assert status.paused
    assert "manual safety stop" in status.blocked_reason


def test_api_rejects_order_submission() -> None:
    api = PaperTradingAPI(_engine_with_cycles(("100",)))

    with pytest.raises(UnsafePaperActionError, match="cannot submit orders"):
        api.submit_order(object())


def _engine_with_cycles(closes: tuple[str, ...]) -> PaperTradingEngine:
    engine = PaperTradingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=PaperTradingConfig(timeframe="1h", order_quantity=Decimal("0.01")),
    )
    for index, close in enumerate(closes):
        engine.on_market_update(_snapshot(index, Decimal(close)))
    return engine


def _snapshot(index: int, close: Decimal) -> PaperMarketSnapshot:
    candle = _candle(index, close)
    received_at = candle.closed_at + timedelta(seconds=1)
    return PaperMarketSnapshot(
        candle=candle,
        order_book_metrics=OrderBookMetrics(
            best_bid=candle.close - Decimal("0.01"),
            best_ask=candle.close + Decimal("0.01"),
            spread=Decimal("0.02"),
            bid_depth=Decimal("5"),
            ask_depth=Decimal("4"),
            imbalance=Decimal("0.1111111111111111111111111111"),
        ),
        health=StreamHealth(
            is_connected=True,
            is_stale=False,
            is_degraded=False,
            disconnect_count=0,
            last_message_at=received_at,
            latency_ms=10,
            stale_after=timedelta(seconds=30),
        ),
        received_at=received_at,
    )


def _candle(index: int, close: Decimal) -> Candle:
    opened_at = NOW + timedelta(hours=index)
    return Candle(
        exchange=Exchange("fixture"),
        pair=PAIR,
        interval="1h",
        opened_at=opened_at,
        closed_at=opened_at + timedelta(hours=1),
        open=close,
        high=close * Decimal("1.005"),
        low=close * Decimal("0.995"),
        close=close,
        volume=Decimal("1"),
    )
