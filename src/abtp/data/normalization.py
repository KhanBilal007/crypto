"""Market data normalization helpers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from abtp.data.scheduler import interval_delta
from abtp.data.symbols import validate_interval
from abtp.domain import Asset, AssetPair, Candle, Exchange
from abtp.domain.models import JsonValue


def normalize_timestamp(value: datetime) -> datetime:
    """Normalize naive or aware timestamps to UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_interval(value: str) -> str:
    """Normalize and validate a candle interval."""

    return validate_interval(value)


def normalize_asset_symbol(value: str) -> str:
    """Normalize an asset symbol for cross-provider comparison."""

    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("asset symbol is required")
    return normalized


def normalize_asset_pair(base: str, quote: str) -> AssetPair:
    """Create a normalized asset pair."""

    return AssetPair(Asset(normalize_asset_symbol(base)), Asset(normalize_asset_symbol(quote)))


def quantize_decimal(value: Decimal | str | int, precision: Decimal) -> Decimal:
    """Quantize a numeric value using conservative half-up rounding."""

    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    if precision <= Decimal("0"):
        raise ValueError("precision must be positive")
    return decimal_value.quantize(precision, rounding=ROUND_HALF_UP)


def normalize_provider_payload(payload: Mapping[str, object]) -> dict[str, JsonValue]:
    """Normalize provider payload shape without allowing arbitrary objects."""

    normalized: dict[str, JsonValue] = {}
    for key, value in payload.items():
        normalized_key = key.strip().lower()
        if not normalized_key:
            raise ValueError("provider payload keys must be non-empty")
        normalized[normalized_key] = _json_value(value)
    return normalized


def normalize_candle(candle: Candle) -> Candle:
    """Normalize timestamps and interval on a candle domain object."""

    return Candle(
        exchange=Exchange(candle.exchange.name),
        pair=candle.pair,
        interval=normalize_interval(candle.interval),
        opened_at=normalize_timestamp(candle.opened_at),
        closed_at=normalize_timestamp(candle.closed_at),
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
    )


def expected_close(opened_at: datetime, interval: str) -> datetime:
    """Return expected close timestamp for a candle interval."""

    return normalize_timestamp(opened_at) + interval_delta(normalize_interval(interval))


def _json_value(value: object) -> JsonValue:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return normalize_timestamp(value).isoformat()
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, Mapping):
        return normalize_provider_payload(value)
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    raise ValueError(f"unsupported provider payload value type: {type(value).__name__}")
