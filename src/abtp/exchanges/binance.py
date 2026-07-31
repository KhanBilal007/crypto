"""Read-only Binance spot market-data adapter."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from abtp.domain import (
    Asset,
    AssetPair,
    Candle,
    Exchange,
    OrderBookLevel,
    OrderBookSnapshot,
    OrderIntent,
)
from abtp.exchanges.base import (
    Balance,
    ExchangeMode,
    ExchangeOrder,
    ExchangeSymbol,
    RateLimitState,
    Ticker,
)
from abtp.exchanges.errors import InvalidSymbolError, UnsupportedOperationError

BINANCE_SPOT_BASE_URL = "https://api.binance.com"
BTC_USDT = AssetPair(Asset("BTC"), Asset("USDT"))


@dataclass(frozen=True, slots=True)
class BinanceSpotMarketDataConfig:
    """Public Binance spot market-data settings."""

    base_url: str = BINANCE_SPOT_BASE_URL
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("base_url is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


class BinanceSpotMarketDataAdapter:
    """Read-only Binance spot adapter for public market data.

    This adapter deliberately does not accept credentials and cannot submit,
    fetch, or cancel real orders.
    """

    def __init__(self, config: BinanceSpotMarketDataConfig | None = None) -> None:
        self._config = config or BinanceSpotMarketDataConfig()
        self._symbols = (_btc_usdt_symbol(),)

    @property
    def name(self) -> str:
        return "binance"

    @property
    def mode(self) -> ExchangeMode:
        return ExchangeMode.PAPER

    def symbols(self) -> tuple[ExchangeSymbol, ...]:
        return self._symbols

    def balances(self) -> tuple[Balance, ...]:
        return ()

    def ticker(self, pair: AssetPair) -> Ticker:
        self._require_symbol(pair)
        captured_at = datetime.now(UTC)
        payload = self._get_json("/api/v3/ticker/price", {"symbol": _binance_symbol(pair)})
        return Ticker(
            pair=pair,
            price=_decimal_field(payload, "price"),
            captured_at=captured_at,
            source_ref=f"binance:spot:ticker:{pair.symbol}:{captured_at.isoformat()}",
        )

    def candles(self, pair: AssetPair, interval: str, limit: int) -> tuple[Candle, ...]:
        self._require_symbol(pair)
        if limit <= 0:
            raise ValueError("limit must be positive")
        raw_klines = self._get_json_array(
            "/api/v3/klines",
            {
                "symbol": _binance_symbol(pair),
                "interval": interval,
                "limit": str(limit + 2),
            },
        )
        captured_at = datetime.now(UTC)
        candles = tuple(
            candle
            for candle in (_kline_to_candle(pair, interval, item) for item in raw_klines)
            if candle.closed_at <= captured_at
        )
        if len(candles) < limit:
            raise ValueError("Binance returned fewer closed candles than requested")
        return candles[-limit:]

    def order_book(self, pair: AssetPair) -> OrderBookSnapshot:
        self._require_symbol(pair)
        captured_at = datetime.now(UTC)
        payload = self._get_json("/api/v3/ticker/bookTicker", {"symbol": _binance_symbol(pair)})
        return OrderBookSnapshot(
            exchange=Exchange(self.name),
            pair=pair,
            captured_at=captured_at,
            bids=(
                OrderBookLevel(
                    price=_decimal_field(payload, "bidPrice"),
                    quantity=_decimal_field(payload, "bidQty"),
                ),
            ),
            asks=(
                OrderBookLevel(
                    price=_decimal_field(payload, "askPrice"),
                    quantity=_decimal_field(payload, "askQty"),
                ),
            ),
            source_ref=f"binance:spot:book:{pair.symbol}:{captured_at.isoformat()}",
        )

    def submit_order(self, _intent: OrderIntent) -> ExchangeOrder:
        raise UnsupportedOperationError("Binance adapter is market-data-only in paper dashboard")

    def get_order(self, _exchange_order_id: str) -> ExchangeOrder:
        raise UnsupportedOperationError("Binance order lookup is disabled in paper dashboard")

    def cancel_order(self, _exchange_order_id: str) -> ExchangeOrder:
        raise UnsupportedOperationError("Binance order cancellation is disabled in paper dashboard")

    def rate_limit_state(self) -> RateLimitState:
        return RateLimitState(limit=1200, remaining=1200, reset_at=datetime.now(UTC))

    def _get_json(self, path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        query = urlencode(params)
        url = f"{self._config.base_url.rstrip('/')}{path}?{query}"
        with urlopen(url, timeout=self._config.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("Binance response must be a JSON object")
        return payload

    def _get_json_array(self, path: str, params: Mapping[str, str]) -> list[Any]:
        query = urlencode(params)
        url = f"{self._config.base_url.rstrip('/')}{path}?{query}"
        with urlopen(url, timeout=self._config.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Binance response must be a JSON array")
        return payload

    def _require_symbol(self, pair: AssetPair) -> None:
        if pair.symbol != BTC_USDT.symbol:
            raise InvalidSymbolError(f"unsupported Binance paper symbol: {pair.symbol}")


def _btc_usdt_symbol() -> ExchangeSymbol:
    return ExchangeSymbol(
        pair=BTC_USDT,
        tick_size=Decimal("0.01"),
        lot_size=Decimal("0.00001"),
        min_order_size=Decimal("0.00001"),
        maker_fee_bps=Decimal("10"),
        taker_fee_bps=Decimal("10"),
    )


def _binance_symbol(pair: AssetPair) -> str:
    return f"{pair.base.symbol}{pair.quote.symbol}"


def _decimal_field(payload: Mapping[str, Any], field: str) -> Decimal:
    value = payload.get(field)
    if value is None:
        raise ValueError(f"Binance response missing {field}")
    return Decimal(str(value))


def _kline_to_candle(pair: AssetPair, interval: str, item: Any) -> Candle:
    if not isinstance(item, list) or len(item) < 6:
        raise ValueError("Binance kline item is malformed")
    opened_at = _from_millis(item[0])
    closed_at = _from_millis(item[6]) if len(item) > 6 else opened_at + timedelta(hours=1)
    return Candle(
        exchange=Exchange("binance"),
        pair=pair,
        interval=interval,
        opened_at=opened_at,
        closed_at=closed_at,
        open=Decimal(str(item[1])),
        high=Decimal(str(item[2])),
        low=Decimal(str(item[3])),
        close=Decimal(str(item[4])),
        volume=Decimal(str(item[5])),
    )


def _from_millis(value: Any) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, UTC)
