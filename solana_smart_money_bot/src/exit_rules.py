from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class OhlcvCandle:
    unix_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class ExitDecision:
    should_exit: bool
    reason: str
    trigger_price: float
    ema: float = 0.0
    vwap: float = 0.0
    latest_volume: float = 0.0
    average_volume: float = 0.0
    trailing_stop: float = 0.0


def normalize_ohlcv_candles(rows: Iterable[dict]) -> list[OhlcvCandle]:
    candles: list[OhlcvCandle] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            unix_time = int(row.get("unixTime") or row.get("time") or row.get("unix_time") or 0)
            open_ = float(row.get("o") or row.get("open") or 0.0)
            high = float(row.get("h") or row.get("high") or 0.0)
            low = float(row.get("l") or row.get("low") or 0.0)
            close = float(row.get("c") or row.get("close") or 0.0)
            volume = float(row.get("v") or row.get("volume") or 0.0)
        except (TypeError, ValueError):
            continue
        if unix_time <= 0 or close <= 0:
            continue
        candles.append(
            OhlcvCandle(
                unix_time=unix_time,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=max(0.0, volume),
            )
        )
    candles.sort(key=lambda c: c.unix_time)
    return candles


def _ema(values: Sequence[float], period: int = 9) -> float:
    if not values:
        return 0.0
    period = max(1, period)
    alpha = 2.0 / (period + 1.0)
    ema = values[0]
    for value in values[1:]:
        ema = (value * alpha) + (ema * (1.0 - alpha))
    return ema


def evaluate_exit_rule(
    candles: Sequence[OhlcvCandle],
    *,
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float,
    peak_price: float,
    trailing_stop_percent: float,
    ema_period: int = 9,
    volume_dying_ratio: float = 0.60,
    min_candles_for_defensive_exit: int = 6,
    max_hold_hours: int = 48,
) -> ExitDecision:
    if not candles:
        return ExitDecision(False, "no_candles", 0.0)

    closes = [c.close for c in candles if c.close > 0]
    if not closes:
        return ExitDecision(False, "no_close_prices", 0.0)

    latest = candles[-1]
    current_price = latest.close
    candle_count = len(candles)
    trailing_stop = max(stop_loss_price, peak_price * (1.0 - trailing_stop_percent / 100.0))
    ema_value = _ema(closes[-max(3, min(len(closes), ema_period * 2)):], period=ema_period)
    total_volume = sum(c.volume for c in candles if c.volume > 0)
    vwap_value = (
        sum(c.close * c.volume for c in candles if c.volume > 0) / total_volume
        if total_volume > 0
        else 0.0
    )

    if latest.low > 0 and latest.low <= stop_loss_price:
        return ExitDecision(True, "stop_loss", stop_loss_price, ema_value, vwap_value, latest.volume, _avg_volume(candles), trailing_stop)
    if latest.high > 0 and latest.high >= take_profit_price:
        return ExitDecision(True, "take_profit", take_profit_price, ema_value, vwap_value, latest.volume, _avg_volume(candles), trailing_stop)
    if peak_price > 0 and current_price <= trailing_stop:
        return ExitDecision(True, "trailing_stop", trailing_stop, ema_value, vwap_value, latest.volume, _avg_volume(candles), trailing_stop)

    avg_volume = _avg_volume(candles)
    volume_dying = (
        candle_count >= min_candles_for_defensive_exit
        and latest.volume > 0
        and avg_volume > 0
        and latest.volume < (avg_volume * volume_dying_ratio)
    )
    below_ema = ema_value > 0 and current_price < ema_value
    below_vwap = vwap_value > 0 and current_price < vwap_value

    if volume_dying and _persistent_below(candles, ema_value, vwap_value):
        return ExitDecision(True, "volume_dying", current_price, ema_value, vwap_value, latest.volume, avg_volume, trailing_stop)
    if candle_count >= min_candles_for_defensive_exit and _persistent_below(candles, ema_value, vwap_value):
        return ExitDecision(True, "ema_vwap_break", current_price, ema_value, vwap_value, latest.volume, avg_volume, trailing_stop)
    if candle_count >= min_candles_for_defensive_exit and _persistent_below_entry(candles, entry_price, threshold=0.97):
        return ExitDecision(True, "momentum_fade", current_price, ema_value, vwap_value, latest.volume, avg_volume, trailing_stop)

    hold_seconds = (latest.unix_time - candles[0].unix_time) if candle_count >= 2 else 0
    if hold_seconds >= max_hold_hours * 3600:
        return ExitDecision(True, "time_exit_48h", current_price, ema_value, vwap_value, latest.volume, avg_volume, trailing_stop)

    return ExitDecision(False, "hold", current_price, ema_value, vwap_value, latest.volume, avg_volume, trailing_stop)


def _avg_volume(candles: Sequence[OhlcvCandle]) -> float:
    volumes = [c.volume for c in candles[:-1] if c.volume > 0]
    if not volumes:
        volumes = [c.volume for c in candles if c.volume > 0]
    return sum(volumes) / len(volumes) if volumes else 0.0


def _persistent_below(candles: Sequence[OhlcvCandle], ema_value: float, vwap_value: float) -> bool:
    if ema_value <= 0 and vwap_value <= 0:
        return False
    recent = list(candles[-3:])
    if len(recent) < 3:
        return False
    count = 0
    for candle in recent:
        if (ema_value > 0 and candle.close < ema_value) or (vwap_value > 0 and candle.close < vwap_value):
            count += 1
    return count >= 2


def _persistent_below_entry(candles: Sequence[OhlcvCandle], entry_price: float, threshold: float) -> bool:
    recent = list(candles[-3:])
    if len(recent) < 3:
        return False
    limit = entry_price * threshold
    count = sum(1 for candle in recent if candle.close < limit)
    return count >= 2
