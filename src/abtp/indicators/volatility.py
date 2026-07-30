"""Volatility and range technical indicators."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from abtp.data import DataQualityStatus
from abtp.domain import Candle
from abtp.indicators.engine import (
    IndicatorResult,
    close_values,
    decimal_mean,
    decimal_parameter,
    decimal_variance,
    indicator_result,
    invalid_numeric_result,
    require_warmup,
    safe_divide,
    true_ranges,
    validate_period,
)

ONE_HUNDRED = Decimal("100")


def atr(
    candles: tuple[Candle, ...],
    *,
    calculated_at: datetime,
    source_quality: DataQualityStatus | None = None,
    period: int = 14,
) -> IndicatorResult:
    """Average true range."""

    period = validate_period(period)
    parameters = {"period": period}
    warmup = require_warmup(
        candles,
        required=period + 1,
        name="atr",
        parameters=parameters,
        lookback=period,
        warmup=period + 1,
        calculated_at=calculated_at,
    )
    if warmup is not None:
        return warmup
    invalid = invalid_numeric_result(
        name="atr",
        parameters=parameters,
        lookback=period,
        warmup=period + 1,
        candles=candles,
        calculated_at=calculated_at,
    )
    if invalid is not None:
        return invalid
    ranges = true_ranges(candles)[-period:]
    return indicator_result(
        name="atr",
        values={"atr": decimal_mean(ranges)},
        parameters=parameters,
        lookback=period,
        warmup=period + 1,
        candles=candles,
        calculated_at=calculated_at,
        source_quality=source_quality,
    )


def bollinger_bands(
    candles: tuple[Candle, ...],
    *,
    calculated_at: datetime,
    source_quality: DataQualityStatus | None = None,
    period: int = 20,
    standard_deviations: Decimal = Decimal("2"),
) -> IndicatorResult:
    """Bollinger bands over close prices."""

    period = validate_period(period)
    deviations = decimal_parameter(standard_deviations, name="standard_deviations")
    if deviations <= Decimal("0"):
        raise ValueError("standard_deviations must be positive")
    parameters = {"period": period, "standard_deviations": deviations}
    warmup = require_warmup(
        candles,
        required=period,
        name="bollinger_bands",
        parameters=parameters,
        lookback=period,
        warmup=period,
        calculated_at=calculated_at,
    )
    if warmup is not None:
        return warmup
    invalid = invalid_numeric_result(
        name="bollinger_bands",
        parameters=parameters,
        lookback=period,
        warmup=period,
        candles=candles,
        calculated_at=calculated_at,
    )
    if invalid is not None:
        return invalid
    closes = close_values(candles)[-period:]
    middle = decimal_mean(closes)
    stddev = decimal_variance(closes, middle).sqrt()
    band_width = stddev * deviations
    return indicator_result(
        name="bollinger_bands",
        values={
            "middle": middle,
            "upper": middle + band_width,
            "lower": middle - band_width,
        },
        parameters=parameters,
        lookback=period,
        warmup=period,
        candles=candles,
        calculated_at=calculated_at,
        source_quality=source_quality,
    )


def adx(
    candles: tuple[Candle, ...],
    *,
    calculated_at: datetime,
    source_quality: DataQualityStatus | None = None,
    period: int = 14,
) -> IndicatorResult:
    """Directional movement strength estimate for the latest window."""

    period = validate_period(period)
    parameters = {"period": period}
    warmup = require_warmup(
        candles,
        required=period + 1,
        name="adx",
        parameters=parameters,
        lookback=period,
        warmup=period + 1,
        calculated_at=calculated_at,
    )
    if warmup is not None:
        return warmup
    invalid = invalid_numeric_result(
        name="adx",
        parameters=parameters,
        lookback=period,
        warmup=period + 1,
        candles=candles,
        calculated_at=calculated_at,
    )
    if invalid is not None:
        return invalid
    window = candles[-(period + 1) :]
    plus_dm = Decimal("0")
    minus_dm = Decimal("0")
    total_tr = Decimal("0")
    previous = window[0]
    for candle in window[1:]:
        up_move = candle.high - previous.high
        down_move = previous.low - candle.low
        if up_move > down_move and up_move > Decimal("0"):
            plus_dm += up_move
        if down_move > up_move and down_move > Decimal("0"):
            minus_dm += down_move
        total_tr += max(
            candle.high - candle.low,
            abs(candle.high - previous.close),
            abs(candle.low - previous.close),
        )
        previous = candle
    plus_di = safe_divide(ONE_HUNDRED * plus_dm, total_tr)
    minus_di = safe_divide(ONE_HUNDRED * minus_dm, total_tr)
    adx_value = safe_divide(ONE_HUNDRED * abs(plus_di - minus_di), plus_di + minus_di)
    return indicator_result(
        name="adx",
        values={"adx": adx_value, "plus_di": plus_di, "minus_di": minus_di},
        parameters=parameters,
        lookback=period,
        warmup=period + 1,
        candles=candles,
        calculated_at=calculated_at,
        source_quality=source_quality,
    )
