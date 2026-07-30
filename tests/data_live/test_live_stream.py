from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection

import pytest

from abtp.data import (
    HeartbeatMonitor,
    LiveMarketDataStream,
    calculate_order_book_metrics,
    diff_order_books,
)
from abtp.domain import Asset, AssetPair, Exchange, OrderBookLevel, OrderBookSnapshot
from abtp.exchanges import (
    SandboxExchangeAdapter,
    UnavailableExchangeError,
    UnsupportedOperationError,
)
from abtp.repositories import MarketDataRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def pair() -> AssetPair:
    return AssetPair(Asset("BTC"), Asset("USDT"))


class ReconnectSandboxAdapter(SandboxExchangeAdapter):
    def __init__(self) -> None:
        super().__init__(now=NOW)
        self.failures_remaining = 1

    def ticker(self, pair: AssetPair):
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise UnavailableExchangeError("fixture disconnect")
        return super().ticker(pair)


def test_live_stream_accepts_and_stores_normalized_updates(
    migrated_connection: Connection,
) -> None:
    stream = LiveMarketDataStream(
        adapter=SandboxExchangeAdapter(now=NOW),
        repository=MarketDataRepository(migrated_connection),
        asset_universe=("BTC", "USDT"),
    )

    update = stream.ingest_once(
        pair=pair(),
        interval="1m",
        now=NOW,
    )

    assert update.accepted is True
    assert update.health.status == "healthy"
    assert update.order_book_metrics.spread == Decimal("2")
    assert migrated_connection.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 1
    assert (
        migrated_connection.execute("SELECT COUNT(*) FROM order_book_snapshots").fetchone()[0] == 1
    )


def test_live_stream_reconnect_simulation_tracks_disconnects(
    migrated_connection: Connection,
) -> None:
    adapter = ReconnectSandboxAdapter()
    stream = LiveMarketDataStream(
        adapter=adapter,
        repository=MarketDataRepository(migrated_connection),
        asset_universe=("BTC", "USDT"),
        max_reconnects=1,
    )

    update = stream.ingest_once(pair=pair(), interval="1m", now=NOW)

    assert update.accepted is True
    assert update.health.disconnect_count == 1
    assert adapter.failures_remaining == 0


def test_stale_and_degraded_heartbeat_status() -> None:
    heartbeat = HeartbeatMonitor(stale_after=timedelta(seconds=10), degraded_latency_ms=50)
    heartbeat.record_message(
        provider_timestamp=NOW,
        received_at=NOW + timedelta(milliseconds=75),
    )

    degraded = heartbeat.health(now=NOW + timedelta(seconds=1))
    stale = heartbeat.health(now=NOW + timedelta(seconds=20))

    assert degraded.status == "degraded"
    assert stale.status == "stale"
    assert stale.is_stale is True


def test_live_stream_marks_degraded_data_unaccepted(migrated_connection: Connection) -> None:
    adapter = SandboxExchangeAdapter(now=NOW)
    stream = LiveMarketDataStream(
        adapter=adapter,
        repository=MarketDataRepository(migrated_connection),
        asset_universe=("BTC", "USDT"),
        degraded_latency_ms=0,
    )

    update = stream.ingest_once(pair=pair(), interval="1m", now=NOW + timedelta(milliseconds=1))

    assert update.accepted is False
    assert update.health.status == "degraded"
    assert migrated_connection.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 0


def test_order_book_metrics_and_delta_consistency() -> None:
    previous = OrderBookSnapshot(
        exchange=Exchange("fixture"),
        pair=pair(),
        captured_at=NOW,
        bids=(
            OrderBookLevel(Decimal("99"), Decimal("1")),
            OrderBookLevel(Decimal("98"), Decimal("2")),
        ),
        asks=(OrderBookLevel(Decimal("101"), Decimal("3")),),
        source_ref="fixture:book:1",
    )
    current = OrderBookSnapshot(
        exchange=Exchange("fixture"),
        pair=pair(),
        captured_at=NOW + timedelta(seconds=1),
        bids=(OrderBookLevel(Decimal("99"), Decimal("2")),),
        asks=(
            OrderBookLevel(Decimal("101"), Decimal("3")),
            OrderBookLevel(Decimal("102"), Decimal("1")),
        ),
        source_ref="fixture:book:2",
    )

    metrics = calculate_order_book_metrics(current)
    delta = diff_order_books(previous, current)

    assert metrics.best_bid == Decimal("99")
    assert metrics.best_ask == Decimal("101")
    assert metrics.bid_depth == Decimal("2")
    assert metrics.ask_depth == Decimal("4")
    assert metrics.imbalance == Decimal("-0.3333333333333333333333333333")
    assert delta.changed_bids == (OrderBookLevel(Decimal("99"), Decimal("2")),)
    assert delta.changed_asks == (OrderBookLevel(Decimal("102"), Decimal("1")),)
    assert delta.removed_bid_prices == (Decimal("98"),)


def test_live_stream_is_read_only(migrated_connection: Connection) -> None:
    stream = LiveMarketDataStream(
        adapter=SandboxExchangeAdapter(now=NOW),
        repository=MarketDataRepository(migrated_connection),
        asset_universe=("BTC", "USDT"),
    )

    with pytest.raises(UnsupportedOperationError, match="read-only"):
        stream.submit_order(object())
