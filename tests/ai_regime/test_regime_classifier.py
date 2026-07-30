from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.ai import (
    MarketRegimeClassifier,
    MarketRegimeLabel,
    RegimeClassification,
    RegimeRuleThresholds,
    classify_market_regime,
)
from abtp.context import ContextFixture, SentimentContextProvider
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, AssetPair
from abtp.features import FEATURE_SCHEMA_VERSION, FeatureSnapshot

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_classifier_labels_trend_range_high_volatility_and_shock() -> None:
    classifier = MarketRegimeClassifier()

    trend_up = classifier.classify(
        _snapshot(
            {
                "market.return_3": Decimal("0.020"),
                "market.close": Decimal("105"),
                "indicator.sma.sma": Decimal("100"),
                "indicator.rsi.rsi": Decimal("60"),
            }
        )
    )
    trend_down = classifier.classify(
        _snapshot(
            {
                "market.return_3": Decimal("-0.020"),
                "market.close": Decimal("95"),
                "indicator.sma.sma": Decimal("100"),
                "indicator.rsi.rsi": Decimal("40"),
            }
        )
    )
    range_bound = classifier.classify(
        _snapshot({"market.return_3": Decimal("0.002"), "indicator.rsi.rsi": Decimal("50")})
    )
    high_volatility = classifier.classify(_snapshot({"indicator.atr.atr_pct": Decimal("0.040")}))
    shock = classifier.classify(_snapshot({"market.return_1": Decimal("-0.090")}))

    assert trend_up.label is MarketRegimeLabel.TREND_UP
    assert trend_up.risk_adjustment.block_new_entries is False
    assert trend_down.label is MarketRegimeLabel.TREND_DOWN
    assert range_bound.label is MarketRegimeLabel.RANGE_BOUND
    assert range_bound.risk_adjustment.reduce_trade_frequency is True
    assert high_volatility.label is MarketRegimeLabel.HIGH_VOLATILITY
    assert high_volatility.risk_adjustment.block_new_entries is True
    assert high_volatility.risk_adjustment.max_position_multiplier == Decimal("0.25")
    assert shock.label is MarketRegimeLabel.SHOCK
    assert shock.risk_adjustment.block_new_entries is True
    assert shock.risk_adjustment.max_position_multiplier == Decimal("0")


def test_boundary_rules_are_deterministic_and_conservative() -> None:
    thresholds = RegimeRuleThresholds()

    high_volatility = classify_market_regime(
        _snapshot({"indicator.atr.atr_pct": thresholds.high_volatility_atr_pct}),
        thresholds=thresholds,
    )
    shock_from_return = classify_market_regime(
        _snapshot({"market.return_1": thresholds.shock_return_abs}),
        thresholds=thresholds,
    )
    shock_from_spread = classify_market_regime(
        _snapshot({"liquidity.spread_bps": thresholds.shock_spread_bps}),
        thresholds=thresholds,
    )

    assert high_volatility.label is MarketRegimeLabel.HIGH_VOLATILITY
    assert high_volatility.risk_adjustment.block_new_entries is True
    assert shock_from_return.label is MarketRegimeLabel.SHOCK
    assert shock_from_spread.label is MarketRegimeLabel.SHOCK


def test_rejected_or_missing_feature_inputs_fail_closed() -> None:
    rejected = classify_market_regime(
        _snapshot(
            {},
            quality=DataQualityStatus(
                trust_level=DataTrustLevel.REJECTED,
                issues=(
                    DataQualityIssue(
                        flag="stale_data",
                        severity=DataTrustLevel.REJECTED,
                        reason="feature source is stale",
                    ),
                ),
                source_ref="features:rejected",
                checked_at=NOW,
            ),
        )
    )
    missing = classify_market_regime(_snapshot({}, omit=("indicator.atr.atr_pct",)))

    assert rejected.label is MarketRegimeLabel.UNKNOWN
    assert rejected.confidence == Decimal("0")
    assert rejected.quality.is_rejected
    assert rejected.risk_adjustment.block_new_entries is True
    assert missing.label is MarketRegimeLabel.UNKNOWN
    assert missing.quality.is_degraded
    assert "missing_regime_feature" in missing.flags
    assert missing.risk_adjustment.block_new_entries is True


def test_low_trust_negative_context_marks_shock_as_degraded_and_blocks() -> None:
    sentiment = SentimentContextProvider(
        fixtures=(
            ContextFixture(
                key="bitcoin_sentiment",
                value=Decimal("-0.80"),
                observed_at=NOW,
                parameter_key="news_sentiment.bitcoin_sentiment",
                confidence=Decimal("0.60"),
            ),
        )
    ).fetch(received_at=NOW + timedelta(minutes=5))

    result = classify_market_regime(
        _snapshot({"market.return_3": Decimal("0.010")}),
        context_batches=(sentiment,),
    )

    assert result.label is MarketRegimeLabel.SHOCK
    assert result.quality.is_degraded
    assert "low_trust_context_used" in result.flags
    assert result.risk_adjustment.block_new_entries is True
    assert any(item.key == "context.bitcoin_sentiment" for item in result.evidence)


def test_regime_transition_sequence_and_public_contract_shape() -> None:
    labels = tuple(
        classify_market_regime(snapshot).label
        for snapshot in (
            _snapshot({"market.return_3": Decimal("0.002"), "indicator.rsi.rsi": Decimal("50")}),
            _snapshot(
                {
                    "market.return_3": Decimal("0.020"),
                    "market.close": Decimal("104"),
                    "indicator.sma.sma": Decimal("100"),
                    "indicator.rsi.rsi": Decimal("58"),
                }
            ),
            _snapshot({"indicator.atr.atr_pct": Decimal("0.040")}),
            _snapshot({"market.return_1": Decimal("-0.090")}),
        )
    )

    assert labels == (
        MarketRegimeLabel.RANGE_BOUND,
        MarketRegimeLabel.TREND_UP,
        MarketRegimeLabel.HIGH_VOLATILITY,
        MarketRegimeLabel.SHOCK,
    )
    assert RegimeClassification.__annotations__.keys() >= {
        "label",
        "confidence",
        "risk_adjustment",
        "reasons",
        "evidence",
        "source_refs",
        "feature_schema_version",
        "generated_at",
        "quality",
    }
    assert "risk_decision" not in RegimeClassification.__annotations__
    assert "order_intent" not in RegimeClassification.__annotations__


def _snapshot(
    overrides: dict[str, Decimal],
    *,
    quality: DataQualityStatus | None = None,
    omit: tuple[str, ...] = (),
) -> FeatureSnapshot:
    values = {
        "market.close": Decimal("100"),
        "market.return_1": Decimal("0.004"),
        "market.return_3": Decimal("0.004"),
        "market.volume_ratio": Decimal("1.0"),
        "indicator.sma.sma": Decimal("100"),
        "indicator.rsi.rsi": Decimal("50"),
        "indicator.atr.atr_pct": Decimal("0.010"),
        "data_quality.flag_count": Decimal("0"),
        "liquidity.spread_bps": Decimal("10"),
    }
    values.update(overrides)
    for key in omit:
        values.pop(key, None)
    return FeatureSnapshot(
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        generated_at=NOW,
        schema_version=FEATURE_SCHEMA_VERSION,
        values=values,
        quality=quality or _trusted_quality(),
        lookback_start=NOW - timedelta(hours=4),
        lookback_end=NOW,
        source_refs={"candles": "fixture:candles:btc-usdt"},
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="features:trusted",
        checked_at=NOW,
    )
