"""Momentum technical indicators."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from abtp.data import DataQualityStatus
from abtp.domain import Candle
from abtp.indicators.engine import (
    IndicatorResult,
    close_values,
    decimal_mean,
    indicator_result,
    invalid_numeric_result,
    require_warmup,
    safe_divide,
    validate_period,
)

ONE_HUNDRED = Decimal("100")


def rsi(
    candles: tuple[Candle, ...],
    *,
    calculated_at: datetime,
    source_quality: DataQualityStatus | None = None,
    period: int = 14,
) -> IndicatorResult:
    """Relative strength index over close-price changes."""

    period = validate_period(period)
    parameters = {"period": period}
    warmup = require_warmup(
        candles,
        required=period + 1,
        name="rsi",
        parameters=parameters,
        lookback=period,
        warmup=period + 1,
        calculated_at=calculated_at,
    )
    if warmup is not None:
        return warmup
    invalid = invalid_numeric_result(
        name="rsi",
        parameters=parameters,
        lookback=period,
        warmup=period + 1,
        candles=candles,
        calculated_at=calculated_at,
    )
    if invalid is not None:
        return invalid
    closes = close_values(candles)[-(period + 1) :]
    changes = tuple(closes[index] - closes[index - 1] for index in range(1, len(closes)))
    gains = tuple(max(change, Decimal("0")) for change in changes)
    losses = tuple(abs(min(change, Decimal("0"))) for change in changes)
    average_gain = decimal_mean(gains)
    average_loss = decimal_mean(losses)
    rsi_value = (
        ONE_HUNDRED
        if average_loss == Decimal("0")
        else ONE_HUNDRED - (ONE_HUNDRED / (Decimal("1") + average_gain / average_loss))
    )
    return indicator_result(
        name="rsi",
        values={"rsi": rsi_value},
        parameters=parameters,
        lookback=period,
        warmup=period + 1,
        candles=candles,
        calculated_at=calculated_at,
        source_quality=source_quality,
    )


def stochastic(
    candles: tuple[Candle, ...],
    *,
    calculated_at: datetime,
    source_quality: DataQualityStatus | None = None,
    period: int = 14,
) -> IndicatorResult:
    """Stochastic oscillator percent K over high/low range."""

    period = validate_period(period)
    parameters = {"period": period}
    warmup = require_warmup(
        candles,
        required=period,
        name="stochastic",
        parameters=parameters,
        lookback=period,
        warmup=period,
        calculated_at=calculated_at,
    )
    if warmup is not None:
        return warmup
    invalid = invalid_numeric_result(
        name="stochastic",
        parameters=parameters,
        lookback=period,
        warmup=period,
        candles=candles,
        calculated_at=calculated_at,
    )
    if invalid is not None:
        return invalid
    window = candles[-period:]
    lowest_low = min(candle.low for candle in window)
    highest_high = max(candle.high for candle in window)
    percent_k = safe_divide(candles[-1].close - lowest_low, highest_high - lowest_low)
    return indicator_result(
        name="stochastic",
        values={"stochastic_k": percent_k * ONE_HUNDRED},
        parameters=parameters,
        lookback=period,
        warmup=period,
        candles=candles,
        calculated_at=calculated_at,
        source_quality=source_quality,
    )
