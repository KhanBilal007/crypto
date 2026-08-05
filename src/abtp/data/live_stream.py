"""Read-only live market data ingestion through exchange adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from abtp.data.heartbeat import HeartbeatMonitor, StreamHealth
from abtp.data.order_book import OrderBookMetrics, calculate_order_book_metrics
from abtp.data.symbols import validate_interval, validate_symbol
from abtp.domain import AssetPair, Candle, OrderBookSnapshot
from abtp.exchanges.base import ExchangeAdapter, Ticker
from abtp.exchanges.errors import ExchangeAdapterError, UnsupportedOperationError
from abtp.repositories.market_data import MarketDataRepository


@dataclass(frozen=True, slots=True)
class LiveMarketDataUpdate:
    """Normalized live data update for future downstream modules."""

    pair: AssetPair
    ticker: Ticker
    candle: Candle | None
    order_book: OrderBookSnapshot
    order_book_metrics: OrderBookMetrics
    health: StreamHealth
    accepted: bool


class LiveMarketDataStream:
    """Poll adapter snapshots and store accepted live market data."""

    def __init__(
        self,
        *,
        adapter: ExchangeAdapter,
        repository: MarketDataRepository,
        asset_universe: tuple[str, ...],
        stale_after: timedelta = timedelta(seconds=30),
        degraded_latency_ms: int = 1000,
        max_reconnects: int = 1,
    ) -> None:
        if max_reconnects < 0:
            raise ValueError("max_reconnects must not be negative")
        self._adapter = adapter
        self._repository = repository
        self._asset_universe = asset_universe
        self._heartbeat = HeartbeatMonitor(
            stale_after=stale_after,
            degraded_latency_ms=degraded_latency_ms,
        )
        self._max_reconnects = max_reconnects

    def ingest_once(
        self,
        *,
        pair: AssetPair,
        interval: str,
        now: datetime,
        store_candle: bool = True,
        store_order_book: bool = True,
    ) -> LiveMarketDataUpdate:
        """Ingest one live snapshot batch through the adapter."""

        normalized_now = _as_utc(now)
        normalized_interval = validate_interval(interval)
        validate_symbol(pair, adapter=self._adapter, asset_universe=self._asset_universe)
        ticker, candle, order_book = self._read_with_reconnect(pair, normalized_interval)
        self._heartbeat.record_message(
            provider_timestamp=ticker.captured_at,
            received_at=normalized_now,
        )
        health = self._heartbeat.health(now=normalized_now)

        if health.is_stale or health.is_degraded:
            accepted = False
        else:
            accepted = True
            if store_candle and candle is not None:
                self._repository.add_candle_if_absent(
                    candle,
                    data_quality_flags={
                        "provider": self._adapter.name,
                        "provider_timestamp": ticker.captured_at.isoformat(),
                        "stream_latency_ms": health.latency_ms,
                        "stream_status": health.status,
                    },
                )
            if store_order_book:
                self._repository.add_order_book(order_book)

        return LiveMarketDataUpdate(
            pair=pair,
            ticker=ticker,
            candle=candle,
            order_book=order_book,
            order_book_metrics=calculate_order_book_metrics(order_book),
            health=health,
            accepted=accepted,
        )

    def health(self, *, now: datetime) -> StreamHealth:
        return self._heartbeat.health(now=now)

    def mark_disconnected(self) -> None:
        self._heartbeat.mark_disconnected()

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject trading actions from live data jobs."""

        raise UnsupportedOperationError("live market data stream is read-only")

    def _read_with_reconnect(
        self, pair: AssetPair, interval: str
    ) -> tuple[Ticker, Candle | None, OrderBookSnapshot]:
        attempts = 0
        while True:
            try:
                ticker = self._adapter.ticker(pair)
                candles = self._adapter.candles(pair, interval, 1)
                order_book = self._adapter.order_book(pair)
                return ticker, candles[-1] if candles else None, order_book
            except ExchangeAdapterError:
                self._heartbeat.mark_disconnected()
                if attempts >= self._max_reconnects:
                    raise
                attempts += 1


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
