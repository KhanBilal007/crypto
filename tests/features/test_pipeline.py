from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.data import (
    DataQualityIssue,
    DataQualityStatus,
    DataTrustLevel,
    OrderBookMetrics,
    StreamHealth,
    evaluate_candles,
)
from abtp.domain import Asset, AssetPair, Candle, Exchange, PortfolioPosition, PortfolioSnapshot
from abtp.features import FeaturePipeline, FeaturePipelineInput
from abtp.indicators import atr, rsi, sma
from abtp.parameters import default_parameter_registry

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def pair() -> AssetPair:
    return AssetPair(Asset("BTC"), Asset("USDT"))


def candles(closes: tuple[str, ...]) -> tuple[Candle, ...]:
    return tuple(
        Candle(
            exchange=Exchange("fixture"),
            pair=pair(),
            interval="1m",
            opened_at=NOW + timedelta(minutes=index),
            closed_at=NOW + timedelta(minutes=index + 1),
            open=Decimal(close),
            high=Decimal(close) + Decimal("1"),
            low=Decimal(close) - Decimal("1"),
            close=Decimal(close),
            volume=Decimal(index + 1),
        )
        for index, close in enumerate(closes)
    )


def trusted_quality(items: tuple[Candle, ...], generated_at: datetime) -> DataQualityStatus:
    return evaluate_candles(
        items,
        interval="1m",
        checked_at=generated_at,
        stale_after=timedelta(minutes=10),
    )


def pipeline_input(
    *,
    generated_at: datetime,
    source_quality: DataQualityStatus | None = None,
) -> FeaturePipelineInput:
    items = candles(("100", "101", "103", "106"))
    quality = source_quality or trusted_quality(items, generated_at)
    indicators = (
        sma(items, calculated_at=generated_at, source_quality=quality, period=3),
        rsi(items, calculated_at=generated_at, source_quality=quality, period=3),
        atr(items, calculated_at=generated_at, source_quality=quality, period=3),
    )
    registry = default_parameter_registry()
    parameter = registry.evaluate_value(
        "price.close",
        value="106",
        observed_at=generated_at,
        checked_at=generated_at,
    )
    portfolio = PortfolioSnapshot(
        captured_at=generated_at,
        positions=(
            PortfolioPosition(
                asset=Asset("BTC"),
                quantity=Decimal("0.25"),
                valuation_quote=Asset("USDT"),
                valuation=Decimal("26.5"),
            ),
            PortfolioPosition(
                asset=Asset("USDT"),
                quantity=Decimal("1000"),
                valuation_quote=Asset("USDT"),
                valuation=Decimal("1000"),
            ),
        ),
        source_ref="portfolio:fixture",
    )
    return FeaturePipelineInput(
        pair=pair(),
        candles=items,
        candle_quality=quality,
        indicator_results=indicators,
        generated_at=generated_at,
        order_book_metrics=OrderBookMetrics(
            best_bid=Decimal("105"),
            best_ask=Decimal("107"),
            spread=Decimal("2"),
            bid_depth=Decimal("5"),
            ask_depth=Decimal("3"),
            imbalance=Decimal("0.25"),
        ),
        stream_health=StreamHealth(
            is_connected=True,
            is_stale=False,
            is_degraded=False,
            disconnect_count=0,
            last_message_at=generated_at,
            latency_ms=12,
            stale_after=timedelta(seconds=30),
        ),
        parameter_values=(parameter,),
        portfolio_snapshot=portfolio,
    )


def test_pipeline_builds_trusted_feature_snapshot_with_expected_values() -> None:
    generated_at = NOW + timedelta(minutes=4)
    snapshot = FeaturePipeline().build(pipeline_input(generated_at=generated_at))

    assert snapshot.is_trusted
    assert snapshot.is_live_eligible
    assert snapshot.schema_version == "stage-015.v1"
    assert snapshot.values["market.close"] == Decimal("106")
    assert snapshot.values["market.return_1"] == Decimal("106") / Decimal("103") - Decimal("1")
    assert snapshot.values["market.return_3"] == Decimal("0.06")
    assert snapshot.values["indicator.rsi.rsi"] == Decimal("100")
    assert snapshot.values["liquidity.imbalance"] == Decimal("0.25")
    assert snapshot.values["portfolio.exposure_base"] == Decimal("0.25")
    assert snapshot.values["data_quality.flag_count"] == Decimal("0")
    assert snapshot.lookback_start == NOW
    assert snapshot.lookback_end == generated_at
    snapshot.require_live_eligible()


def test_pipeline_is_reproducible_and_backfill_live_logic_matches() -> None:
    generated_at = NOW + timedelta(minutes=4)
    pipeline = FeaturePipeline()

    historical = pipeline.build(pipeline_input(generated_at=generated_at))
    live = pipeline.build(pipeline_input(generated_at=generated_at))

    assert historical.values == live.values
    assert historical.metadata_json() == live.metadata_json()


def test_pipeline_rejects_future_source_data_to_prevent_leakage() -> None:
    generated_at = NOW + timedelta(minutes=3)
    snapshot = FeaturePipeline().build(pipeline_input(generated_at=generated_at))

    assert snapshot.is_rejected
    assert snapshot.values == {}
    assert snapshot.flags == ("future_candle",)
    with pytest.raises(ValueError, match="not live-eligible"):
        snapshot.require_live_eligible()


def test_untrusted_sources_make_feature_vectors_non_actionable() -> None:
    generated_at = NOW + timedelta(minutes=4)
    quality = DataQualityStatus(
        trust_level=DataTrustLevel.DEGRADED,
        issues=(
            DataQualityIssue(
                flag="missing_candle_gap",
                severity=DataTrustLevel.DEGRADED,
                reason="fixture gap",
            ),
        ),
        source_ref="candles:fixture",
        checked_at=generated_at,
    )

    snapshot = FeaturePipeline().build(
        pipeline_input(generated_at=generated_at, source_quality=quality)
    )

    assert snapshot.is_degraded
    assert not snapshot.is_live_eligible
    assert "missing_candle_gap" in snapshot.flags
    assert snapshot.values["data_quality.flag_count"] > Decimal("0")


def test_missing_required_indicator_rejects_snapshot() -> None:
    generated_at = NOW + timedelta(minutes=4)
    base = pipeline_input(generated_at=generated_at)
    snapshot = FeaturePipeline().build(
        FeaturePipelineInput(
            pair=base.pair,
            candles=base.candles,
            candle_quality=base.candle_quality,
            indicator_results=(),
            generated_at=generated_at,
        )
    )

    assert snapshot.is_rejected
    assert "missing_required_feature" in snapshot.flags
