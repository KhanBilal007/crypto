from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, AssetPair, Candle, Exchange
from abtp.indicators import IndicatorEngine, default_indicator_engine, sma

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def pair() -> AssetPair:
    return AssetPair(Asset("BTC"), Asset("USDT"))


def candles(closes: tuple[Decimal, ...]) -> tuple[Candle, ...]:
    return tuple(
        Candle(
            exchange=Exchange("fixture"),
            pair=pair(),
            interval="1m",
            opened_at=NOW + timedelta(minutes=index),
            closed_at=NOW + timedelta(minutes=index + 1),
            open=close,
            high=close + Decimal("1"),
            low=close - Decimal("1"),
            close=close,
            volume=Decimal(index + 1),
        )
        for index, close in enumerate(closes)
    )


def test_default_engine_registers_stage_014_indicators() -> None:
    engine = default_indicator_engine()

    assert engine.names() == (
        "adx",
        "atr",
        "bollinger_bands",
        "ema",
        "macd",
        "obv",
        "rsi",
        "sma",
        "stochastic",
        "support_resistance",
        "vwap",
    )


def test_engine_dispatches_by_name_and_keeps_metadata() -> None:
    engine = IndicatorEngine()
    engine.register("SMA", sma)

    result = engine.calculate("sma", candles((Decimal("1"), Decimal("2"), Decimal("3"))), period=3)

    assert result.values == {"sma": Decimal("2")}
    assert result.metadata.name == "sma"
    assert result.metadata.parameters == {"period": 3}
    assert result.metadata.version == "stage-014"
    assert result.is_trusted


def test_engine_rejects_duplicate_and_unknown_indicators() -> None:
    engine = IndicatorEngine()
    engine.register("sma", sma)

    with pytest.raises(ValueError, match="already registered"):
        engine.register("SMA", sma)
    with pytest.raises(KeyError, match="unknown indicator"):
        engine.calculate("nope", candles((Decimal("1"),)))


def test_indicator_results_are_not_executable_order_objects() -> None:
    result = sma(candles((Decimal("1"), Decimal("2"), Decimal("3"))), calculated_at=NOW, period=3)

    assert not hasattr(result, "side")
    assert not hasattr(result, "quantity")
    assert not hasattr(result, "risk_decision")


def test_source_quality_degrades_or_rejects_indicator_output() -> None:
    degraded_quality = DataQualityStatus(
        trust_level=DataTrustLevel.DEGRADED,
        issues=(
            DataQualityIssue(
                flag="missing_candle_gap",
                severity=DataTrustLevel.DEGRADED,
                reason="fixture gap",
            ),
        ),
        source_ref="candles:fixture",
        checked_at=NOW,
    )
    rejected_quality = DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="stale_data",
                severity=DataTrustLevel.REJECTED,
                reason="fixture stale",
            ),
        ),
        source_ref="candles:fixture",
        checked_at=NOW,
    )

    degraded = sma(
        candles((Decimal("1"), Decimal("2"), Decimal("3"))),
        calculated_at=NOW,
        source_quality=degraded_quality,
        period=3,
    )
    rejected = sma(
        candles((Decimal("1"), Decimal("2"), Decimal("3"))),
        calculated_at=NOW,
        source_quality=rejected_quality,
        period=3,
    )

    assert degraded.is_degraded
    assert degraded.values == {"sma": Decimal("2")}
    assert degraded.flags == ("missing_candle_gap",)
    assert rejected.is_rejected
    assert rejected.values == {}
    assert rejected.flags == ("stale_data",)


def test_insufficient_and_invalid_numeric_inputs_fail_closed() -> None:
    short_result = sma(candles((Decimal("1"), Decimal("2"))), calculated_at=NOW, period=3)
    bad_candle = candles((Decimal("1"), Decimal("2"), Decimal("3")))[-1]
    object.__setattr__(bad_candle, "close", Decimal("NaN"))
    bad_result = sma(
        (*candles((Decimal("1"), Decimal("2"))), bad_candle),
        calculated_at=NOW,
        period=3,
    )

    assert short_result.is_rejected
    assert short_result.flags == ("insufficient_data",)
    assert bad_result.is_rejected
    assert bad_result.flags == ("invalid_numeric_value",)
