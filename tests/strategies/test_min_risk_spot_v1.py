from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.ai import (
    BaselineModelMetadata,
    BaselinePrediction,
    MarketRegimeClassifier,
    PredictionExplanation,
    PredictionServiceResult,
)
from abtp.data import DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, AssetPair, SignalDirection
from abtp.features import FEATURE_SCHEMA_VERSION, FeatureSnapshot
from abtp.strategies import (
    MIN_RISK_SPOT_STRATEGY_NAME,
    MIN_RISK_SPOT_STRATEGY_VERSION,
    MinRiskSpotRuntimeState,
    MinRiskSpotStrategyV1,
    StrategyContext,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_valid_btc_setup_emits_non_executable_buy_signal_with_stop_and_target() -> None:
    strategy = MinRiskSpotStrategyV1()
    context = _context(prediction=_prediction(probability_up=Decimal("0.65")))

    evaluation = strategy.evaluate(context)

    assert evaluation.strategy_name == MIN_RISK_SPOT_STRATEGY_NAME
    assert evaluation.strategy_version == MIN_RISK_SPOT_STRATEGY_VERSION
    assert evaluation.signal.direction is SignalDirection.BUY
    assert evaluation.signal.confidence == Decimal("0.40")
    assert evaluation.plan.stop_suggestion == Decimal("98.000")
    assert evaluation.plan.target_suggestion == Decimal("104.000")
    assert evaluation.is_trade_signal
    assert not hasattr(evaluation, "order_intent")
    assert not hasattr(evaluation, "risk_decision")
    assert not hasattr(evaluation, "exchange_order")


def test_bad_regime_rejects_new_long_entry() -> None:
    strategy = MinRiskSpotStrategyV1()
    context = _context(
        snapshot=_snapshot(return_1=Decimal("-0.09")),
        prediction=_prediction(probability_up=Decimal("0.65")),
    )

    evaluation = strategy.evaluate(context)

    assert evaluation.signal.direction is SignalDirection.HOLD
    assert "regime is not acceptable for new long entries" in evaluation.reasons
    assert evaluation.plan.stop_suggestion is None
    assert evaluation.plan.target_suggestion is None


def test_unclear_setup_rejects_more_often_than_it_trades() -> None:
    strategy = MinRiskSpotStrategyV1()
    contexts = (
        _context(snapshot=_snapshot(return_3=Decimal("0.002"))),
        _context(snapshot=_snapshot(rsi=Decimal("75"))),
        _context(snapshot=_snapshot(volume_ratio=Decimal("0.40"))),
        _context(snapshot=_snapshot(spread_bps=Decimal("80"))),
        _context(snapshot=_snapshot(atr_pct=Decimal("0.050"))),
        _context(prediction=_prediction(probability_up=Decimal("0.40"))),
    )

    evaluations = tuple(strategy.evaluate(context) for context in contexts)

    assert all(evaluation.signal.direction is SignalDirection.HOLD for evaluation in evaluations)
    assert any("trend confirmation is below threshold" in item.reasons for item in evaluations)
    assert any(
        "RSI momentum filter is not in conservative range" in item.reasons for item in evaluations
    )
    assert any("volume confirmation is below threshold" in item.reasons for item in evaluations)
    assert any("spread exceeds ceiling" in item.reasons for item in evaluations)
    assert any("ATR volatility exceeds conservative limit" in item.reasons for item in evaluations)
    assert any(
        "AI upward probability is below optional confirmation threshold" in item.reasons
        for item in evaluations
    )


def test_cooldown_after_loss_blocks_trade() -> None:
    strategy = MinRiskSpotStrategyV1(
        runtime_state=MinRiskSpotRuntimeState(last_loss_at=NOW - timedelta(hours=1))
    )

    evaluation = strategy.evaluate(_context(prediction=_prediction(probability_up=Decimal("0.65"))))

    assert evaluation.signal.direction is SignalDirection.HOLD
    assert "loss cooldown is active" in evaluation.reasons


def test_no_averaging_down_when_open_position_exists() -> None:
    strategy = MinRiskSpotStrategyV1(
        runtime_state=MinRiskSpotRuntimeState(open_base_position=Decimal("0.01"))
    )

    evaluation = strategy.evaluate(_context(prediction=_prediction(probability_up=Decimal("0.65"))))

    assert evaluation.signal.direction is SignalDirection.HOLD
    assert "existing BTC position blocks averaging down" in evaluation.reasons


def test_strategy_is_long_only_and_never_emits_sell() -> None:
    strategy = MinRiskSpotStrategyV1()

    evaluation = strategy.evaluate(_context(prediction=_prediction(probability_up=Decimal("0.10"))))

    assert evaluation.signal.direction is SignalDirection.HOLD
    assert evaluation.signal.direction is not SignalDirection.SELL
    assert "AI upward probability is below optional confirmation threshold" in evaluation.reasons


def _context(
    *,
    snapshot: FeatureSnapshot | None = None,
    prediction: PredictionServiceResult | None = None,
) -> StrategyContext:
    feature_snapshot = snapshot or _snapshot()
    return StrategyContext(
        features=feature_snapshot,
        generated_at=NOW,
        timeframe="1h",
        prediction=prediction,
        regime=MarketRegimeClassifier().classify(feature_snapshot),
    )


def _snapshot(
    *,
    return_1: Decimal = Decimal("0.01"),
    return_3: Decimal = Decimal("0.02"),
    rsi: Decimal = Decimal("58"),
    volume_ratio: Decimal = Decimal("1.10"),
    spread_bps: Decimal = Decimal("10"),
    atr_pct: Decimal = Decimal("0.010"),
) -> FeatureSnapshot:
    return FeatureSnapshot(
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        generated_at=NOW,
        schema_version=FEATURE_SCHEMA_VERSION,
        values={
            "market.close": Decimal("100"),
            "market.return_1": return_1,
            "market.return_3": return_3,
            "market.volume_ratio": volume_ratio,
            "indicator.sma.sma": Decimal("99"),
            "indicator.rsi.rsi": rsi,
            "indicator.atr.atr_pct": atr_pct,
            "data_quality.flag_count": Decimal("0"),
            "liquidity.spread_bps": spread_bps,
        },
        quality=_trusted_quality(),
        lookback_start=NOW - timedelta(hours=4),
        lookback_end=NOW,
        source_refs={"candles": "fixture:candles:min-risk"},
    )


def _prediction(*, probability_up: Decimal) -> PredictionServiceResult:
    snapshot = _snapshot()
    probability_down = Decimal("1") - probability_up
    baseline_prediction = BaselinePrediction(
        pair_symbol=snapshot.pair.symbol,
        generated_at=NOW,
        model_metadata=BaselineModelMetadata(
            model_name="fixture_model",
            version="stage-021.fixture",
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            trained_at=NOW - timedelta(hours=1),
            training_start=NOW - timedelta(days=2),
            training_end=NOW - timedelta(hours=1),
            label_horizon_steps=1,
            metrics={"accuracy": Decimal("0")},
            limitations=("fixture only",),
        ),
        features_ref=snapshot.inputs_ref,
        probability_up=probability_up,
        probability_down=probability_down,
        confidence=Decimal("0.40"),
        expected_return=Decimal("0.01"),
        expected_volatility=Decimal("0.02"),
        quality=_trusted_quality(),
        actionable=True,
        rationale="fixture prediction",
    )
    explanation = PredictionExplanation(
        model_name="fixture_model",
        model_version="stage-021.fixture",
        features_ref=snapshot.inputs_ref,
        summary="fixture explanation",
        feature_importance=(),
        data_quality_score=Decimal("1"),
        source_refs=snapshot.source_refs,
        generated_at=NOW,
        quality=_trusted_quality(),
        limitations=("fixture only",),
    )
    return PredictionServiceResult(
        prediction=baseline_prediction,
        explanation=explanation,
        actionable=True,
        non_actionable_reasons=(),
        generated_at=NOW,
        quality=_trusted_quality(),
        prediction_ref="fixture:prediction",
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:trusted",
        checked_at=NOW,
    )
