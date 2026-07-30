"""Symbol and interval validation for historical data collection."""

from __future__ import annotations

from abtp.domain import AssetPair
from abtp.exchanges.base import ExchangeAdapter
from abtp.exchanges.errors import InvalidSymbolError

SUPPORTED_CANDLE_INTERVALS: frozenset[str] = frozenset({"1m", "5m", "15m", "1h", "4h", "1d"})


def validate_interval(interval: str) -> str:
    """Validate and normalize a candle interval."""

    normalized = interval.strip()
    if normalized not in SUPPORTED_CANDLE_INTERVALS:
        raise ValueError(f"unsupported candle interval: {interval}")
    return normalized


def validate_symbol(
    pair: AssetPair,
    *,
    adapter: ExchangeAdapter,
    asset_universe: tuple[str, ...],
) -> AssetPair:
    """Validate pair against configured assets and exchange metadata."""

    configured_assets = {asset.upper() for asset in asset_universe}
    if pair.base.symbol not in configured_assets or pair.quote.symbol not in configured_assets:
        raise InvalidSymbolError(f"symbol {pair.symbol} is outside configured asset universe")
    supported = {symbol.pair.symbol for symbol in adapter.symbols()}
    if pair.symbol not in supported:
        raise InvalidSymbolError(f"symbol {pair.symbol} is not supported by adapter {adapter.name}")
    return pair
