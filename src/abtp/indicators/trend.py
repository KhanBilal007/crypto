"""Trend and volume-oriented technical indicators."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from abtp.data import DataQualityStatus
from abtp.domain import Candle
from abtp.indicators.engine import (
    IndicatorResult,
    close_values,
    decimal_mean,
    ema_series,
    indicator_result,
    invalid_numeric_result,
    require_warmup,
    validate_period,
)


def sma(
    candles: tuple[Candle, ...],
    *,
    calculated_at: datetime,
    source_quality: DataQualityStatus | None = None,
    period: int = 20,
) -> IndicatorResult:
    """Simple moving average of close prices."""

    period = validate_period(period)
    parameters = {"period": period}
    warmup = require_warmup(
        candles,
        required=period,
        name="sma",
        parameters=parameters,
        lookback=period,
        warmup=period,
        calculated_at=calculated_at,
    )
    if warmup is not None:
        return warmup
    invalid = invalid_numeric_result(
        name="sma",
        parameters=parameters,
        lookback=period,
        warmup=period,
        candles=candles,
        calculated_at=calculated_at,
    )
    if invalid is not None:
        return invalid
    values = close_values(candles)[-period:]
    return indicator_result(
        name="sma",
        values={"sma": decimal_mean(values)},
        parameters=parameters,
        lookback=period,
        warmup=period,
        candles=candles,
        calculated_at=calculated_at,
        source_quality=source_quality,
    )


def ema(
    candles: tuple[Candle, ...],
    *,
    calculated_at: datetime,
    source_quality: DataQualityStatus | None = None,
    period: int = 20,
) -> IndicatorResult:
    """Exponential moving average of close prices."""

    period = validate_period(period)
    parameters = {"period": period}
    warmup = require_warmup(
        candles,
        required=period,
        name="ema",
        parameters=parameters,
        lookback=period,
        warmup=period,
        calculated_at=calculated_at,
    )
    if warmup is not None:
        return warmup
    invalid = invalid_numeric_result(
        name="ema",
        parameters=parameters,
        lookback=period,
        warmup=period,
        candles=candles,
        calculated_at=calculated_at,
    )
    if invalid is not None:
        return invalid
    return indicator_result(
        name="ema",
        values={"ema": ema_series(close_values(candles), period)[-1]},
        parameters=parameters,
        lookback=period,
        warmup=period,
        candles=candles,
        calculated_at=calculated_at,
        source_quality=source_quality,
    )


def macd(
    candles: tuple[Candle, ...],
    *,
    calculated_at: datetime,
    source_quality: DataQualityStatus | None = None,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> IndicatorResult:
    """Moving average convergence/divergence over close prices."""

    fast_period = validate_period(fast_period, name="fast_period")
    slow_period = validate_period(slow_period, name="slow_period")
    signal_period = validate_period(signal_period, name="signal_period")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be less than slow_period")
    warmup_length = slow_period + signal_period
    parameters = {
        "fast_period": fast_period,
        "slow_period": slow_period,
        "signal_period": signal_period,
    }
    warmup = require_warmup(
        candles,
        required=warmup_length,
        name="macd",
        parameters=parameters,
        lookback=warmup_length,
        warmup=warmup_length,
        calculated_at=calculated_at,
    )
    if warmup is not None:
        return warmup
    invalid = invalid_numeric_result(
        name="macd",
        parameters=parameters,
        lookback=warmup_length,
        warmup=warmup_length,
        candles=candles,
        calculated_at=calculated_at,
    )
    if invalid is not None:
        return invalid
    closes = close_values(candles)
    fast = ema_series(closes, fast_period)
    slow = ema_series(closes, slow_period)
    macd_values = tuple(
        fast_value - slow_value for fast_value, slow_value in zip(fast, slow, strict=True)
    )
    signal = ema_series(macd_values, signal_period)[-1]
    macd_value = macd_values[-1]
    return indicator_result(
        name="macd",
        values={"macd": macd_value, "signal": signal, "histogram": macd_value - signal},
        parameters=parameters,
        lookback=warmup_length,
        warmup=warmup_length,
        candles=candles,
        calculated_at=calculated_at,
        source_quality=source_quality,
    )


def vwap(
    candles: tuple[Candle, ...],
    *,
    calculated_at: datetime,
    source_quality: DataQualityStatus | None = None,
    period: int = 20,
) -> IndicatorResult:
    """Volume-weighted average price over the requested window."""

    period = validate_period(period)
    parameters = {"period": period}
    warmup = require_warmup(
        candles,
        required=period,
        name="vwap",
        parameters=parameters,
        lookback=period,
        warmup=period,
        calculated_at=calculated_at,
    )
    if warmup is not None:
        return warmup
    invalid = invalid_numeric_result(
        name="vwap",
        parameters=parameters,
        lookback=period,
        warmup=period,
        candles=candles,
        calculated_at=calculated_at,
    )
    if invalid is not None:
        return invalid
    window = candles[-period:]
    weighted = sum(
        ((candle.high + candle.low + candle.close) / Decimal("3")) * candle.volume
        for candle in window
    )
    volume = sum((candle.volume for candle in window), Decimal("0"))
    if volume == Decimal("0"):
        return _zero_volume_result(candles, calculated_at, parameters, "vwap", period)
    return indicator_result(
        name="vwap",
        values={"vwap": weighted / volume},
        parameters=parameters,
        lookback=period,
        warmup=period,
        candles=candles,
        calculated_at=calculated_at,
        source_quality=source_quality,
    )


def obv(
    candles: tuple[Candle, ...],
    *,
    calculated_at: datetime,
    source_quality: DataQualityStatus | None = None,
) -> IndicatorResult:
    """On-balance volume from close direction and volume."""

    parameters: dict[str, object] = {}
    warmup = require_warmup(
        candles,
        required=2,
        name="obv",
        parameters=parameters,
        lookback=2,
        warmup=2,
        calculated_at=calculated_at,
    )
    if warmup is not None:
        return warmup
    invalid = invalid_numeric_result(
        name="obv",
        parameters=parameters,
        lookback=2,
        warmup=2,
        candles=candles,
        calculated_at=calculated_at,
    )
    if invalid is not None:
        return invalid
    value = Decimal("0")
    previous = candles[0]
    for candle in candles[1:]:
        if candle.close > previous.close:
            value += candle.volume
        elif candle.close < previous.close:
            value -= candle.volume
        previous = candle
    return indicator_result(
        name="obv",
        values={"obv": value},
        parameters=parameters,
        lookback=len(candles),
        warmup=2,
        candles=candles,
        calculated_at=calculated_at,
        source_quality=source_quality,
    )


def support_resistance(
    candles: tuple[Candle, ...],
    *,
    calculated_at: datetime,
    source_quality: DataQualityStatus | None = None,
    lookback: int = 20,
) -> IndicatorResult:
    """Window high/low levels for future strategy consumers."""

    lookback = validate_period(lookback, name="lookback")
    parameters = {"lookback": lookback}
    warmup = require_warmup(
        candles,
        required=lookback,
        name="support_resistance",
        parameters=parameters,
        lookback=lookback,
        warmup=lookback,
        calculated_at=calculated_at,
    )
    if warmup is not None:
        return warmup
    invalid = invalid_numeric_result(
        name="support_resistance",
        parameters=parameters,
        lookback=lookback,
        warmup=lookback,
        candles=candles,
        calculated_at=calculated_at,
    )
    if invalid is not None:
        return invalid
    window = candles[-lookback:]
    return indicator_result(
        name="support_resistance",
        values={
            "support": min(candle.low for candle in window),
            "resistance": max(candle.high for candle in window),
        },
        parameters=parameters,
        lookback=lookback,
        warmup=lookback,
        candles=candles,
        calculated_at=calculated_at,
        source_quality=source_quality,
    )


def _zero_volume_result(
    candles: tuple[Candle, ...],
    calculated_at: datetime,
    parameters: Mapping[str, object],
    name: str,
    period: int,
) -> IndicatorResult:
    from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
    from abtp.indicators.engine import IndicatorResult, metadata_for

    metadata = metadata_for(
        name=name,
        parameters=parameters,
        lookback=period,
        warmup=period,
        candles=candles,
        calculated_at=calculated_at,
    )
    issue = DataQualityIssue(
        flag="zero_volume",
        severity=DataTrustLevel.REJECTED,
        reason=f"{name} cannot be calculated when volume is zero",
    )
    return IndicatorResult(
        metadata=metadata,
        values={},
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.REJECTED,
            issues=(issue,),
            source_ref=f"indicator:{name}:{metadata.source_interval}",
            checked_at=metadata.calculated_at,
        ),
    )
