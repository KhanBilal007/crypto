"""Technical indicator result contracts and registry engine."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain import Candle
from abtp.domain.models import JsonValue

INDICATOR_VERSION = "stage-014"
IndicatorCalculator = Callable[..., "IndicatorResult"]


@dataclass(frozen=True, slots=True)
class IndicatorMetadata:
    """Trace metadata for one deterministic indicator calculation."""

    name: str
    parameters: Mapping[str, JsonValue]
    lookback: int
    warmup: int
    source_interval: str
    calculated_at: datetime
    version: str = INDICATOR_VERSION

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("indicator name is required")
        if self.lookback <= 0:
            raise ValueError("indicator lookback must be positive")
        if self.warmup <= 0:
            raise ValueError("indicator warmup must be positive")
        object.__setattr__(self, "calculated_at", normalize_timestamp(self.calculated_at))


@dataclass(frozen=True, slots=True)
class IndicatorResult:
    """Indicator values with source-quality status and audit-friendly metadata."""

    metadata: IndicatorMetadata
    values: Mapping[str, Decimal]
    quality: DataQualityStatus

    @property
    def is_trusted(self) -> bool:
        return self.quality.is_trusted

    @property
    def is_degraded(self) -> bool:
        return self.quality.is_degraded

    @property
    def is_rejected(self) -> bool:
        return self.quality.is_rejected

    @property
    def flags(self) -> tuple[str, ...]:
        return self.quality.flags


class IndicatorEngine:
    """Registry for pure indicator calculators.

    The engine does not know about strategies, predictions, risk checks, orders,
    exchange clients, or repositories. It only dispatches named calculations
    over normalized candle objects.
    """

    def __init__(self) -> None:
        self._calculators: dict[str, IndicatorCalculator] = {}

    def register(self, name: str, calculator: IndicatorCalculator) -> None:
        cleaned = _indicator_name(name)
        if cleaned in self._calculators:
            raise ValueError(f"indicator already registered: {cleaned}")
        self._calculators[cleaned] = calculator

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._calculators))

    def calculate(
        self,
        name: str,
        candles: tuple[Candle, ...],
        *,
        calculated_at: datetime | None = None,
        source_quality: DataQualityStatus | None = None,
        **parameters: object,
    ) -> IndicatorResult:
        cleaned = _indicator_name(name)
        try:
            calculator = self._calculators[cleaned]
        except KeyError as exc:
            raise KeyError(f"unknown indicator: {cleaned}") from exc
        return calculator(
            candles,
            calculated_at=calculated_at or datetime.now(UTC),
            source_quality=source_quality,
            **parameters,
        )


def default_indicator_engine() -> IndicatorEngine:
    """Build the default Stage 014 indicator registry."""

    from abtp.indicators.momentum import rsi, stochastic
    from abtp.indicators.trend import ema, macd, obv, sma, support_resistance, vwap
    from abtp.indicators.volatility import adx, atr, bollinger_bands

    engine = IndicatorEngine()
    registrations = (
        ("sma", sma),
        ("ema", ema),
        ("macd", macd),
        ("vwap", vwap),
        ("obv", obv),
        ("support_resistance", support_resistance),
        ("rsi", rsi),
        ("stochastic", stochastic),
        ("atr", atr),
        ("bollinger_bands", bollinger_bands),
        ("adx", adx),
    )
    for name, calculator in registrations:
        calculator = cast(IndicatorCalculator, calculator)
        engine.register(name, calculator)
    return engine


def indicator_result(
    *,
    name: str,
    values: Mapping[str, Decimal],
    parameters: Mapping[str, object],
    lookback: int,
    warmup: int,
    candles: tuple[Candle, ...],
    calculated_at: datetime,
    source_quality: DataQualityStatus | None,
) -> IndicatorResult:
    """Create a result while preserving degraded source status."""

    metadata = metadata_for(
        name=name,
        parameters=parameters,
        lookback=lookback,
        warmup=warmup,
        candles=candles,
        calculated_at=calculated_at,
    )
    quality = quality_from_source(name, metadata, source_quality)
    if quality.is_rejected:
        return IndicatorResult(metadata=metadata, values={}, quality=quality)
    return IndicatorResult(metadata=metadata, values=dict(values), quality=quality)


def insufficient_data_result(
    *,
    name: str,
    required: int,
    received: int,
    parameters: Mapping[str, object],
    lookback: int,
    warmup: int,
    candles: tuple[Candle, ...],
    calculated_at: datetime,
) -> IndicatorResult:
    """Return an explicit fail-closed result for warmup-window failures."""

    metadata = metadata_for(
        name=name,
        parameters=parameters,
        lookback=lookback,
        warmup=warmup,
        candles=candles,
        calculated_at=calculated_at,
    )
    issue = DataQualityIssue(
        flag="insufficient_data",
        severity=DataTrustLevel.REJECTED,
        reason=f"{name} requires {required} candles but received {received}",
    )
    return IndicatorResult(
        metadata=metadata,
        values={},
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.REJECTED,
            issues=(issue,),
            source_ref=f"indicator:{metadata.name}:{metadata.source_interval}",
            checked_at=metadata.calculated_at,
        ),
    )


def invalid_numeric_result(
    *,
    name: str,
    parameters: Mapping[str, object],
    lookback: int,
    warmup: int,
    candles: tuple[Candle, ...],
    calculated_at: datetime,
) -> IndicatorResult | None:
    """Return a rejected result if candle numeric fields are not finite."""

    bad_fields = []
    for index, candle in enumerate(candles):
        for field_name, value in {
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }.items():
            if not value.is_finite():
                bad_fields.append(f"{index}.{field_name}")
    if not bad_fields:
        return None
    metadata = metadata_for(
        name=name,
        parameters=parameters,
        lookback=lookback,
        warmup=warmup,
        candles=candles,
        calculated_at=calculated_at,
    )
    issue = DataQualityIssue(
        flag="invalid_numeric_value",
        severity=DataTrustLevel.REJECTED,
        reason=f"{name} received non-finite candle values: {', '.join(bad_fields)}",
    )
    return IndicatorResult(
        metadata=metadata,
        values={},
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.REJECTED,
            issues=(issue,),
            source_ref=f"indicator:{metadata.name}:{metadata.source_interval}",
            checked_at=metadata.calculated_at,
        ),
    )


def validate_period(period: int, *, name: str = "period") -> int:
    if period <= 0:
        raise ValueError(f"{name} must be positive")
    return period


def latest_interval(candles: tuple[Candle, ...]) -> str:
    return candles[-1].interval if candles else "unknown"


def decimal_parameter(value: object, *, name: str) -> Decimal:
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be decimal-compatible") from exc


def metadata_for(
    *,
    name: str,
    parameters: Mapping[str, object],
    lookback: int,
    warmup: int,
    candles: tuple[Candle, ...],
    calculated_at: datetime,
) -> IndicatorMetadata:
    return IndicatorMetadata(
        name=_indicator_name(name),
        parameters={key: _json_parameter(value) for key, value in parameters.items()},
        lookback=lookback,
        warmup=warmup,
        source_interval=latest_interval(candles),
        calculated_at=calculated_at,
    )


def quality_from_source(
    name: str,
    metadata: IndicatorMetadata,
    source_quality: DataQualityStatus | None,
) -> DataQualityStatus:
    source_ref = f"indicator:{name}:{metadata.source_interval}:{metadata.calculated_at.isoformat()}"
    if source_quality is None:
        return DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref=source_ref,
            checked_at=metadata.calculated_at,
        )
    return DataQualityStatus(
        trust_level=source_quality.trust_level,
        issues=source_quality.issues,
        source_ref=f"{source_ref}:source={source_quality.source_ref}",
        checked_at=metadata.calculated_at,
    )


def _indicator_name(name: str) -> str:
    cleaned = name.strip().lower()
    if not cleaned:
        raise ValueError("indicator name is required")
    return cleaned


def _json_parameter(value: object) -> JsonValue:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def require_warmup(
    candles: tuple[Candle, ...],
    *,
    required: int,
    name: str,
    parameters: Mapping[str, object],
    lookback: int,
    warmup: int,
    calculated_at: datetime,
) -> IndicatorResult | None:
    if len(candles) >= required:
        return None
    return insufficient_data_result(
        name=name,
        required=required,
        received=len(candles),
        parameters=parameters,
        lookback=lookback,
        warmup=warmup,
        candles=candles,
        calculated_at=calculated_at,
    )


def close_values(candles: tuple[Candle, ...]) -> tuple[Decimal, ...]:
    return tuple(candle.close for candle in candles)


def true_ranges(candles: tuple[Candle, ...]) -> tuple[Decimal, ...]:
    ranges: list[Decimal] = []
    previous_close = candles[0].close
    for candle in candles[1:]:
        ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        )
        previous_close = candle.close
    return tuple(ranges)


def ema_series(values: tuple[Decimal, ...], period: int) -> tuple[Decimal, ...]:
    validate_period(period)
    multiplier = Decimal("2") / Decimal(period + 1)
    current = values[0]
    series = [current]
    for value in values[1:]:
        current = (value - current) * multiplier + current
        series.append(current)
    return tuple(series)


def decimal_mean(values: tuple[Decimal, ...]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def decimal_variance(values: tuple[Decimal, ...], mean: Decimal) -> Decimal:
    return sum((value - mean) ** 2 for value in values) / Decimal(len(values))


def safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == Decimal("0"):
        return Decimal("0")
    return numerator / denominator
