from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection

import pytest

from abtp.data import HistoricalMarketDataCollector, plan_backfill_windows
from abtp.domain import Asset, AssetPair, Candle, Exchange
from abtp.exchanges import (
    Balance,
    ExchangeMode,
    ExchangeOrder,
    ExchangeSymbol,
    InvalidSymbolError,
    RateLimitState,
    SandboxExchangeAdapter,
    Ticker,
    UnavailableExchangeError,
    UnsupportedOperationError,
)
from abtp.exchanges.base import ExchangeAdapter
from abtp.repositories.market_data import MarketDataRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def pair() -> AssetPair:
    return AssetPair(Asset("BTC"), Asset("USDT"))


def candle(opened_at: datetime, *, interval: str = "1m") -> Candle:
    return Candle(
        exchange=Exchange("fixture"),
        pair=pair(),
        interval=interval,
        opened_at=opened_at,
        closed_at=opened_at + timedelta(minutes=1),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("1"),
    )


class PagedCandleAdapter:
    name = "paged-fixture"
    mode = ExchangeMode.SANDBOX

    def __init__(self, pages: tuple[tuple[Candle, ...], ...]) -> None:
        self.pages = pages
        self.calls = 0

    def symbols(self) -> tuple[ExchangeSymbol, ...]:
        return (_symbol(),)

    def candles(self, pair: AssetPair, interval: str, limit: int) -> tuple[Candle, ...]:
        page = self.pages[self.calls % len(self.pages)]
        self.calls += 1
        return page[:limit]

    def balances(self) -> tuple[Balance, ...]:
        return ()

    def ticker(self, pair: AssetPair) -> Ticker:
        raise NotImplementedError

    def order_book(self, pair: AssetPair) -> object:
        raise NotImplementedError

    def submit_order(self, intent: object) -> ExchangeOrder:
        raise AssertionError("collector must not submit orders")

    def get_order(self, exchange_order_id: str) -> ExchangeOrder:
        raise NotImplementedError

    def cancel_order(self, exchange_order_id: str) -> ExchangeOrder:
        raise NotImplementedError

    def rate_limit_state(self) -> RateLimitState:
        return RateLimitState(100, 100, NOW)


class RetryCandleAdapter(PagedCandleAdapter):
    def candles(self, pair: AssetPair, interval: str, limit: int) -> tuple[Candle, ...]:
        if self.calls == 0:
            self.calls += 1
            raise UnavailableExchangeError("fixture unavailable")
        return super().candles(pair, interval, limit)


def test_backfill_paginates_and_stores_candles_idempotently(
    migrated_connection: Connection,
) -> None:
    start = NOW
    end = NOW + timedelta(minutes=4)
    pages = (
        (candle(start), candle(start + timedelta(minutes=1))),
        (candle(start + timedelta(minutes=2)), candle(start + timedelta(minutes=3))),
    )
    adapter: ExchangeAdapter = PagedCandleAdapter(pages)
    collector = HistoricalMarketDataCollector(
        adapter=adapter,
        repository=MarketDataRepository(migrated_connection),
        asset_universe=("BTC", "USDT"),
    )

    first = collector.backfill(pair=pair(), interval="1m", start=start, end=end, page_size=2)
    second = collector.backfill(pair=pair(), interval="1m", start=start, end=end, page_size=2)

    assert first.fetched == 4
    assert first.inserted == 4
    assert first.duplicates == 0
    assert first.data_quality_flags == ()
    assert second.inserted == 0
    assert second.duplicates == 4
    assert migrated_connection.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 4


def test_gap_duplicate_and_timestamp_quality_flags_are_detected(
    migrated_connection: Connection,
) -> None:
    start = NOW
    end = NOW + timedelta(minutes=4)
    pages = (
        (
            candle(start),
            candle(start),
            candle(start + timedelta(minutes=3)),
        ),
    )
    collector = HistoricalMarketDataCollector(
        adapter=PagedCandleAdapter(pages),
        repository=MarketDataRepository(migrated_connection),
        asset_universe=("BTC", "USDT"),
    )

    result = collector.backfill(pair=pair(), interval="1m", start=start, end=end, page_size=4)

    assert "duplicate_provider_candle" in result.data_quality_flags
    assert "missing_candle" in result.data_quality_flags
    assert "timestamp_order_error" in result.data_quality_flags


def test_timezone_normalization_and_provider_payload_are_stored(
    migrated_connection: Connection,
) -> None:
    naive_start = datetime(2026, 1, 1)
    collector = HistoricalMarketDataCollector(
        adapter=PagedCandleAdapter(((candle(naive_start),),)),
        repository=MarketDataRepository(migrated_connection),
        asset_universe=("BTC", "USDT"),
    )

    collector.backfill(
        pair=pair(),
        interval="1m",
        start=naive_start,
        end=naive_start + timedelta(minutes=1),
        page_size=1,
    )
    row = migrated_connection.execute(
        "SELECT opened_at, data_quality_flags FROM candles LIMIT 1"
    ).fetchone()

    assert str(row["opened_at"]).endswith("+00:00")
    assert "raw_payload" in str(row["data_quality_flags"])
    assert "provider_timestamp" in str(row["data_quality_flags"])


def test_retry_behavior_for_transient_adapter_error(migrated_connection: Connection) -> None:
    adapter = RetryCandleAdapter(((candle(NOW),),))
    collector = HistoricalMarketDataCollector(
        adapter=adapter,
        repository=MarketDataRepository(migrated_connection),
        asset_universe=("BTC", "USDT"),
        max_retries=1,
    )

    result = collector.backfill(
        pair=pair(),
        interval="1m",
        start=NOW,
        end=NOW + timedelta(minutes=1),
        page_size=1,
    )

    assert result.retries == 1
    assert result.inserted == 1


def test_symbol_interval_validation_and_read_only_guard(migrated_connection: Connection) -> None:
    collector = HistoricalMarketDataCollector(
        adapter=SandboxExchangeAdapter(now=NOW),
        repository=MarketDataRepository(migrated_connection),
        asset_universe=("BTC", "USDT"),
    )

    with pytest.raises(ValueError, match="unsupported candle interval"):
        collector.backfill(
            pair=pair(),
            interval="30m",
            start=NOW,
            end=NOW + timedelta(minutes=1),
        )
    with pytest.raises(InvalidSymbolError, match="asset universe"):
        collector.backfill(
            pair=AssetPair(Asset("ETH"), Asset("USDT")),
            interval="1m",
            start=NOW,
            end=NOW + timedelta(minutes=1),
        )
    with pytest.raises(UnsupportedOperationError, match="read-only"):
        collector.submit_order(object())


def test_backfill_window_planning_for_supported_intervals() -> None:
    windows = plan_backfill_windows(
        start=NOW,
        end=NOW + timedelta(minutes=45),
        interval="15m",
        page_size=2,
    )

    assert [window.limit for window in windows] == [2, 1]
    assert windows[0].start == NOW
    assert windows[0].end == NOW + timedelta(minutes=30)


def _symbol() -> ExchangeSymbol:
    return ExchangeSymbol(
        pair=pair(),
        tick_size=Decimal("0.01"),
        lot_size=Decimal("0.0001"),
        min_order_size=Decimal("0.0001"),
        maker_fee_bps=Decimal("10"),
        taker_fee_bps=Decimal("20"),
    )
