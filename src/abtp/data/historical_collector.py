"""Read-only historical OHLCV candle collector."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from sqlite3 import IntegrityError

from abtp.data.scheduler import BackfillWindow, interval_delta, plan_backfill_windows
from abtp.data.symbols import validate_interval, validate_symbol
from abtp.domain import AssetPair, Candle
from abtp.exchanges.base import ExchangeAdapter
from abtp.exchanges.errors import ExchangeAdapterError, UnsupportedOperationError
from abtp.repositories.market_data import MarketDataRepository


@dataclass(frozen=True, slots=True)
class BackfillResult:
    """Collection result with quality counts for observability."""

    pair: AssetPair
    interval: str
    requested_windows: tuple[BackfillWindow, ...]
    fetched: int
    inserted: int
    duplicates: int
    missing: int
    timestamp_errors: int
    retries: int
    data_quality_flags: tuple[str, ...]


class HistoricalMarketDataCollector:
    """Collect and store historical candles through an exchange adapter only."""

    def __init__(
        self,
        *,
        adapter: ExchangeAdapter,
        repository: MarketDataRepository,
        asset_universe: tuple[str, ...],
        max_retries: int = 1,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        self._adapter = adapter
        self._repository = repository
        self._asset_universe = asset_universe
        self._max_retries = max_retries

    def backfill(
        self,
        *,
        pair: AssetPair,
        interval: str,
        start: datetime,
        end: datetime,
        page_size: int = 100,
    ) -> BackfillResult:
        """Backfill candles idempotently for a pair and interval."""

        normalized_interval = validate_interval(interval)
        validate_symbol(pair, adapter=self._adapter, asset_universe=self._asset_universe)
        windows = plan_backfill_windows(
            start=start,
            end=end,
            interval=normalized_interval,
            page_size=page_size,
        )

        fetched = inserted = duplicates = missing = timestamp_errors = retries = 0
        flags: set[str] = set()
        expected_delta = interval_delta(normalized_interval)

        for window in windows:
            candles, retry_count = self._fetch_with_retry(pair, normalized_interval, window.limit)
            retries += retry_count
            fetched += len(candles)
            window_flags = _quality_flags(
                candles=tuple(_normalize_candle(candle) for candle in candles),
                start=window.start,
                end=window.end,
                expected_delta=expected_delta,
            )
            flags.update(window_flags)
            missing += window_flags.count("missing_candle")
            timestamp_errors += window_flags.count("timestamp_order_error")

            for candle in candles:
                normalized = _normalize_candle(candle)
                try:
                    added = self._repository.add_candle_if_absent(
                        normalized,
                        data_quality_flags={
                            "provider": self._adapter.name,
                            "provider_timestamp": normalized.closed_at.isoformat(),
                            "flags": list(window_flags),
                            "raw_payload": normalized.to_json_dict(),
                        },
                    )
                except IntegrityError:
                    added = False
                if added:
                    inserted += 1
                else:
                    duplicates += 1

        return BackfillResult(
            pair=pair,
            interval=normalized_interval,
            requested_windows=windows,
            fetched=fetched,
            inserted=inserted,
            duplicates=duplicates,
            missing=missing,
            timestamp_errors=timestamp_errors,
            retries=retries,
            data_quality_flags=tuple(sorted(flags)),
        )

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject trading actions from data jobs."""

        raise UnsupportedOperationError("historical data collector is read-only")

    def _fetch_with_retry(
        self, pair: AssetPair, interval: str, limit: int
    ) -> tuple[tuple[Candle, ...], int]:
        attempts = 0
        while True:
            try:
                return self._adapter.candles(pair, interval, limit), attempts
            except ExchangeAdapterError:
                if attempts >= self._max_retries:
                    raise
                attempts += 1


def _normalize_candle(candle: Candle) -> Candle:
    opened_at = _as_utc(candle.opened_at)
    closed_at = _as_utc(candle.closed_at)
    if opened_at == candle.opened_at and closed_at == candle.closed_at:
        return candle
    return Candle(
        exchange=candle.exchange,
        pair=candle.pair,
        interval=candle.interval,
        opened_at=opened_at,
        closed_at=closed_at,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
    )


def _quality_flags(
    *,
    candles: tuple[Candle, ...],
    start: datetime,
    end: datetime,
    expected_delta: timedelta,
) -> tuple[str, ...]:
    flags: list[str] = []
    if not candles:
        return ("missing_candle",)

    previous: Candle | None = None
    seen_open_times: set[datetime] = set()
    for candle in candles:
        if candle.opened_at in seen_open_times:
            flags.append("duplicate_provider_candle")
        seen_open_times.add(candle.opened_at)
        if candle.closed_at - candle.opened_at != expected_delta:
            flags.append("timestamp_order_error")
        if candle.opened_at < _as_utc(start) or candle.closed_at > _as_utc(end):
            flags.append("out_of_window")
        if previous is not None:
            if candle.opened_at <= previous.opened_at:
                flags.append("timestamp_order_error")
            if candle.opened_at - previous.opened_at != expected_delta:
                flags.append("missing_candle")
        previous = candle

    if candles[0].opened_at > _as_utc(start) or candles[-1].closed_at < _as_utc(end):
        flags.append("missing_candle")
    return tuple(flags)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
