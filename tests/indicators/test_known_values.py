from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.domain import Asset, AssetPair, Candle, Exchange
from abtp.indicators import (
    adx,
    atr,
    bollinger_bands,
    ema,
    macd,
    obv,
    rsi,
    sma,
    stochastic,
    support_resistance,
    vwap,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def pair() -> AssetPair:
    return AssetPair(Asset("BTC"), Asset("USDT"))


def candle_at(
    index: int,
    close: Decimal,
    *,
    high: Decimal | None = None,
    low: Decimal | None = None,
    volume: Decimal | None = None,
) -> Candle:
    return Candle(
        exchange=Exchange("fixture"),
        pair=pair(),
        interval="1m",
        opened_at=NOW + timedelta(minutes=index),
        closed_at=NOW + timedelta(minutes=index + 1),
        open=close,
        high=high or close + Decimal("1"),
        low=low or close - Decimal("1"),
        close=close,
        volume=volume or Decimal(index + 1),
    )


def series(closes: tuple[str, ...]) -> tuple[Candle, ...]:
    return tuple(candle_at(index, Decimal(close)) for index, close in enumerate(closes))


def test_sma_ema_and_macd_known_values() -> None:
    rising = series(("1", "2", "3", "4", "5"))
    constant = series(("10", "10", "10", "10", "10", "10"))

    assert sma(rising, calculated_at=NOW, period=3).values["sma"] == Decimal("4")
    assert ema(rising, calculated_at=NOW, period=3).values["ema"] == Decimal("4.0625")

    macd_result = macd(
        constant,
        calculated_at=NOW,
        fast_period=2,
        slow_period=3,
        signal_period=2,
    )
    assert macd_result.values == {
        "macd": Decimal("0"),
        "signal": Decimal("0"),
        "histogram": Decimal("0"),
    }


def test_rsi_stochastic_obv_and_vwap_known_values() -> None:
    rising = series(("1", "2", "3", "4", "5"))
    fixed_price = tuple(
        candle_at(index, Decimal("10"), high=Decimal("11"), low=Decimal("9"), volume=Decimal("2"))
        for index in range(3)
    )

    assert rsi(rising, calculated_at=NOW, period=3).values["rsi"] == Decimal("100")
    assert stochastic(rising, calculated_at=NOW, period=3).values["stochastic_k"] == Decimal(
        "75.00"
    )
    assert obv(rising, calculated_at=NOW).values["obv"] == Decimal("14")
    assert vwap(fixed_price, calculated_at=NOW, period=3).values["vwap"] == Decimal("10")


def test_atr_bollinger_adx_and_support_resistance_known_values() -> None:
    flat = tuple(
        candle_at(index, Decimal("10"), high=Decimal("11"), low=Decimal("9"), volume=Decimal("1"))
        for index in range(5)
    )
    rising = series(("1", "2", "3", "4", "5"))

    assert atr(flat, calculated_at=NOW, period=3).values["atr"] == Decimal("2")
    bands = bollinger_bands(flat, calculated_at=NOW, period=3)
    assert bands.values == {
        "middle": Decimal("10"),
        "upper": Decimal("10"),
        "lower": Decimal("10"),
    }
    adx_result = adx(rising, calculated_at=NOW, period=3)
    assert adx_result.values["adx"] == Decimal("100")
    levels = support_resistance(rising, calculated_at=NOW, lookback=3)
    assert levels.values == {"support": Decimal("2"), "resistance": Decimal("6")}
