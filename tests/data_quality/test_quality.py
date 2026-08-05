from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from abtp.data import DataTrustLevel, evaluate_candles, evaluate_order_book, evaluate_stream_health
from abtp.data.anomaly import AnomalyThresholds, provider_disagreement_bps, spread_bps
from abtp.data.heartbeat import HeartbeatMonitor
from abtp.data.normalization import (
    normalize_asset_pair,
    normalize_asset_symbol,
    normalize_provider_payload,
    normalize_timestamp,
    quantize_decimal,
)
from abtp.domain import Asset, AssetPair, Candle, Exchange, OrderBookLevel, OrderBookSnapshot

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def pair() -> AssetPair:
    return AssetPair(Asset("BTC"), Asset("USDT"))


def candle(
    opened_at: datetime,
    *,
    close: Decimal = Decimal("100"),
    volume: Decimal = Decimal("1"),
) -> Candle:
    return Candle(
        exchange=Exchange("fixture"),
        pair=pair(),
        interval="1m",
        opened_at=opened_at,
        closed_at=opened_at + timedelta(minutes=1),
        open=close,
        high=close + Decimal("1"),
        low=close - Decimal("1"),
        close=close,
        volume=volume,
    )


def book(*, bid: Decimal = Decimal("99"), ask: Decimal = Decimal("101")) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        exchange=Exchange("fixture"),
        pair=pair(),
        captured_at=NOW,
        bids=(OrderBookLevel(bid, Decimal("1")),),
        asks=(OrderBookLevel(ask, Decimal("1")),),
        source_ref="fixture:book",
    )


def test_trusted_candles_have_traceable_status() -> None:
    status = evaluate_candles(
        (candle(NOW), candle(NOW + timedelta(minutes=1))),
        interval="1m",
        checked_at=NOW + timedelta(minutes=2),
        stale_after=timedelta(minutes=5),
    )

    assert status.trust_level is DataTrustLevel.TRUSTED
    assert status.flags == ()
    assert status.source_ref.startswith("candles:BTC/USDT:1m:")
    status.require_trusted()


def test_missing_duplicate_zero_volume_and_outlier_flags_degrade_or_reject() -> None:
    status = evaluate_candles(
        (
            candle(NOW, close=Decimal("100")),
            candle(NOW, close=Decimal("100"), volume=Decimal("0")),
            candle(NOW + timedelta(minutes=3), close=Decimal("200")),
        ),
        interval="1m",
        checked_at=NOW + timedelta(minutes=4),
        stale_after=timedelta(minutes=5),
    )

    assert status.is_rejected
    assert "duplicate_timestamp" in status.flags
    assert "timestamp_order_error" in status.flags
    assert "zero_volume" in status.flags
    assert "missing_candle_gap" in status.flags
    assert "outlier_return" in status.flags
    with pytest.raises(ValueError, match="data quality is rejected"):
        status.require_trusted()


def test_stale_and_provider_disagreement_flags() -> None:
    status = evaluate_candles(
        (candle(NOW, close=Decimal("100")),),
        interval="1m",
        checked_at=NOW + timedelta(hours=1),
        stale_after=timedelta(minutes=5),
        provider_prices=(Decimal("120"),),
    )

    assert status.is_rejected
    assert "stale_data" in status.flags
    assert "provider_disagreement" in status.flags
    assert provider_disagreement_bps(Decimal("100"), Decimal("101")) == Decimal("100.00")


def test_order_book_abnormal_spread_and_stale_status() -> None:
    status = evaluate_order_book(
        book(bid=Decimal("90"), ask=Decimal("110")),
        checked_at=NOW + timedelta(minutes=10),
        stale_after=timedelta(seconds=30),
        thresholds=AnomalyThresholds(max_spread_bps=Decimal("100")),
    )

    assert status.is_rejected
    assert "abnormal_spread" in status.flags
    assert "stale_data" in status.flags
    assert spread_bps(book(bid=Decimal("99"), ask=Decimal("101"))) == Decimal("200.00")


def test_stream_health_degraded_and_stale_status() -> None:
    heartbeat = HeartbeatMonitor(stale_after=timedelta(seconds=1), degraded_latency_ms=5)
    heartbeat.record_message(
        provider_timestamp=NOW,
        received_at=NOW + timedelta(milliseconds=10),
    )

    degraded = evaluate_stream_health(heartbeat.health(now=NOW), checked_at=NOW)
    stale = evaluate_stream_health(
        heartbeat.health(now=NOW + timedelta(seconds=2)),
        checked_at=NOW + timedelta(seconds=2),
    )

    assert degraded.is_degraded
    assert "degraded_feed" in degraded.flags
    assert stale.is_rejected
    assert "stale_data" in stale.flags


def test_normalization_helpers_and_malformed_payloads() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    timestamp = datetime(2026, 1, 1, 5, 30, tzinfo=ist)

    assert normalize_timestamp(timestamp) == NOW
    assert normalize_asset_symbol(" btc ") == "BTC"
    assert normalize_asset_pair("btc", "usdt").symbol == "BTC/USDT"
    assert quantize_decimal("1.234", Decimal("0.01")) == Decimal("1.23")
    assert normalize_provider_payload(
        {
            " Price ": Decimal("100.5"),
            "Seen At": NOW,
            "nested": {"Volume": Decimal("1")},
        }
    ) == {
        "price": "100.5",
        "seen at": NOW.isoformat(),
        "nested": {"volume": "1"},
    }
    with pytest.raises(ValueError, match="provider payload keys"):
        normalize_provider_payload({"": "bad"})
    with pytest.raises(ValueError, match="unsupported provider payload"):
        normalize_provider_payload({"bad": object()})
