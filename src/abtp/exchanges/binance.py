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
    OrderSide,
    Trade,
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
ETH_USDT = AssetPair(Asset("ETH"), Asset("USDT"))
SOL_USDT = AssetPair(Asset("SOL"), Asset("USDT"))
BINANCE_SPOT_PAIRS = (BTC_USDT, ETH_USDT, SOL_USDT)


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
        self._symbols = tuple(_spot_symbol(pair) for pair in BINANCE_SPOT_PAIRS)

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

    def price_change_24h_pct(self, pair: AssetPair) -> Decimal:
        """Return Binance's public 24h price-change percentage for a spot pair."""

        self._require_symbol(pair)
        payload = self._get_json("/api/v3/ticker/24hr", {"symbol": _binance_symbol(pair)})
        return _decimal_field(payload, "priceChangePercent")

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
        payload = self._get_json(
            "/api/v3/depth",
            {"symbol": _binance_symbol(pair), "limit": "10"},
        )
        return OrderBookSnapshot(
            exchange=Exchange(self.name),
            pair=pair,
            captured_at=captured_at,
            bids=_order_book_levels(payload, "bids"),
            asks=_order_book_levels(payload, "asks"),
            source_ref=f"binance:spot:book:{pair.symbol}:{captured_at.isoformat()}",
        )

    def trades(self, pair: AssetPair, start: datetime, end: datetime) -> tuple[Trade, ...]:
        """Return recent public aggregate trades for spot market observation."""

        self._require_symbol(pair)
        if end <= start:
            raise ValueError("trade end must be after start")
        payload = self._get_json_array(
            "/api/v3/aggTrades",
            {
                "symbol": _binance_symbol(pair),
                "startTime": str(_to_millis(start)),
                "endTime": str(_to_millis(end)),
                "limit": "20",
            },
        )
        return tuple(_agg_trade_to_trade(pair, item) for item in payload[-20:])

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
        if pair.symbol not in {item.symbol for item in BINANCE_SPOT_PAIRS}:
            raise InvalidSymbolError(f"unsupported Binance paper symbol: {pair.symbol}")


def _spot_symbol(pair: AssetPair) -> ExchangeSymbol:
    return ExchangeSymbol(
        pair=pair,
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


def _order_book_levels(payload: Mapping[str, Any], side: str) -> tuple[OrderBookLevel, ...]:
    raw_levels = payload.get(side)
    if not isinstance(raw_levels, list) or not raw_levels:
        raise ValueError(f"Binance depth response missing {side}")
    levels = []
    for item in raw_levels:
        if not isinstance(item, list | tuple) or len(item) < 2:
            raise ValueError(f"Binance depth {side} level is malformed")
        levels.append(OrderBookLevel(price=Decimal(str(item[0])), quantity=Decimal(str(item[1]))))
    return tuple(levels)


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


def _to_millis(value: datetime) -> int:
    active = value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return int(active.timestamp() * 1000)


def _agg_trade_to_trade(pair: AssetPair, item: Any) -> Trade:
    if not isinstance(item, Mapping):
        raise ValueError("Binance aggregate trade item is malformed")
    is_buyer_maker = bool(item.get("m", False))
    return Trade(
        exchange=Exchange("binance"),
        pair=pair,
        traded_at=_from_millis(item["T"]),
        price=Decimal(str(item["p"])),
        quantity=Decimal(str(item["q"])),
        side=OrderSide.SELL if is_buyer_maker else OrderSide.BUY,
        trade_id=str(item["a"]),
    )
