from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.data import OrderBookMetrics, StreamHealth
from abtp.domain import Asset, AssetPair, Candle, Exchange
from abtp.observability import MetricsRegistry, record_paper_cycle_metrics
from abtp.paper import PaperMarketSnapshot, PaperTradingConfig, PaperTradingEngine
from abtp.strategies import MinRiskSpotStrategyV1

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PAIR = AssetPair(Asset("BTC"), Asset("USDT"))


def test_metric_registry_records_paper_cycle_metrics() -> None:
    engine = PaperTradingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=PaperTradingConfig(timeframe="1h"),
    )
    cycle = engine.on_market_update(_snapshot(0, Decimal("100"), latency_ms=42))
    registry = MetricsRegistry()

    points = record_paper_cycle_metrics(registry, cycle)

    assert registry.latest("abtp_data_latency_ms").value == Decimal("42")  # type: ignore[union-attr]
    assert registry.latest("abtp_paper_equity") is not None
    assert points[0].labels["component"] == "paper"


def test_blocked_cycle_emits_blocked_trade_counter() -> None:
    engine = PaperTradingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=PaperTradingConfig(timeframe="1h"),
    )
    cycle = engine.on_market_update(_snapshot(0, Decimal("100"), stale=True))
    registry = MetricsRegistry()

    record_paper_cycle_metrics(registry, cycle)

    blocked = registry.latest("abtp_blocked_trade_count")
    assert blocked is not None
    assert blocked.value == Decimal("1")
    assert blocked.labels["reason"] == "live data is stale"


def test_metric_labels_reject_secret_like_keys_without_value_leakage() -> None:
    registry = MetricsRegistry()

    with pytest.raises(ValueError) as exc_info:
        registry.gauge(
            "abtp_fixture",
            value=Decimal("1"),
            observed_at=NOW,
            labels={"api_key": "do-not-leak"},
        )

    assert "api_key" in str(exc_info.value)
    assert "do-not-leak" not in str(exc_info.value)


def _snapshot(
    index: int,
    close: Decimal,
    *,
    latency_ms: int = 10,
    stale: bool = False,
) -> PaperMarketSnapshot:
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
            is_connected=not stale,
            is_stale=stale,
            is_degraded=stale,
            disconnect_count=1 if stale else 0,
            last_message_at=received_at,
            latency_ms=latency_ms,
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
