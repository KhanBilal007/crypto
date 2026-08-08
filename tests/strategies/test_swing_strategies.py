from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.ai import MarketRegimeClassifier
from abtp.data import DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, AssetPair, SignalDirection
from abtp.features import FEATURE_SCHEMA_VERSION, FeatureSnapshot
from abtp.strategies import (
    BreakoutStrategy,
    StrategyContext,
    SupportResistanceReboundStrategy,
    TrendPullbackStrategy,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
PAIR = AssetPair(Asset("BTC"), Asset("USDT"))


def test_trend_pullback_strategy_buys_confirmed_pullback() -> None:
    evaluation = TrendPullbackStrategy().evaluate(
        _context(
            close=Decimal("100"),
            ema_9=Decimal("103"),
            ema_21=Decimal("98"),
            resistance=Decimal("104"),
            pullback=Decimal("0.038"),
            rsi=Decimal("52"),
        )
    )

    assert evaluation.signal.direction is SignalDirection.BUY
    assert evaluation.plan.stop_suggestion is not None
    assert evaluation.plan.target_suggestion is not None


def test_breakout_strategy_requires_resistance_break_and_volume() -> None:
    evaluation = BreakoutStrategy().evaluate(
        _context(
            close=Decimal("106"),
            resistance=Decimal("104"),
            volume_ratio=Decimal("1.35"),
        )
    )

    assert evaluation.signal.direction is SignalDirection.BUY
    assert "resistance breakout" in evaluation.reasons[0]


def test_support_rebound_strategy_buys_near_support() -> None:
    evaluation = SupportResistanceReboundStrategy().evaluate(
        _context(
            close=Decimal("101"),
            support=Decimal("100"),
            resistance=Decimal("115"),
            rsi=Decimal("44"),
        )
    )

    assert evaluation.signal.direction is SignalDirection.BUY
    assert "support rebound" in evaluation.reasons[0]


def _context(
    *,
    close: Decimal,
    ema_9: Decimal = Decimal("101"),
    ema_21: Decimal = Decimal("100"),
    ema_50: Decimal = Decimal("95"),
    support: Decimal = Decimal("96"),
    resistance: Decimal = Decimal("105"),
    pullback: Decimal = Decimal("0.02"),
    rsi: Decimal = Decimal("50"),
    volume_ratio: Decimal = Decimal("1.2"),
) -> StrategyContext:
    snapshot = FeatureSnapshot(
        pair=PAIR,
        generated_at=NOW,
        schema_version=FEATURE_SCHEMA_VERSION,
        values={
            "market.close": close,
            "market.return_1": Decimal("0.01"),
            "market.return_3": Decimal("0.02"),
            "market.volume_ratio": volume_ratio,
            "market.support_20": support,
            "market.resistance_20": resistance,
            "market.pullback_from_high_pct": pullback,
            "indicator.sma.sma": ema_21,
            "indicator.ema_9": ema_9,
            "indicator.ema_21": ema_21,
            "indicator.ema_50": ema_50,
            "indicator.rsi.rsi": rsi,
            "indicator.atr.atr_pct": Decimal("0.01"),
            "data_quality.flag_count": Decimal("0"),
            "liquidity.spread_bps": Decimal("5"),
        },
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref="fixture:swing",
            checked_at=NOW,
        ),
        lookback_start=NOW - timedelta(days=3),
        lookback_end=NOW,
        source_refs={"candles": "fixture:swing"},
    )
    return StrategyContext(
        features=snapshot,
        generated_at=NOW,
        timeframe="1h",
        regime=MarketRegimeClassifier().classify(snapshot),
    )
