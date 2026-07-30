from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection

from abtp.ai import (
    BaselineModelMetadata,
    BaselinePrediction,
    MarketRegimeClassifier,
    PredictionExplanation,
    PredictionServiceResult,
)
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, AssetPair, SignalDirection
from abtp.features import FEATURE_SCHEMA_VERSION, FeatureSnapshot
from abtp.repositories import AuditRepository, IntelligenceRepository
from abtp.strategies import (
    StrategyContext,
    StrategyEngine,
    StrategyEngineConfig,
    StrategyRegistry,
    ThresholdRuleStrategy,
    ThresholdRuleStrategyConfig,
    build_registry,
    strategy_names,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_strategy_registry_evaluates_multiple_strategies_in_name_order() -> None:
    registry = build_registry(
        (
            _strategy("zeta", buy_threshold=Decimal("0.95")),
            _strategy("alpha", buy_threshold=Decimal("0.60")),
        )
    )
    engine = StrategyEngine(
        registry,
        config=StrategyEngineConfig(persist_signals=False, audit_signals=False),
    )

    evaluations = engine.evaluate_all(
        _context(prediction=_prediction(probability_up=Decimal("0.70")))
    )

    assert strategy_names(registry) == ("alpha", "zeta")
    assert tuple(evaluation.strategy_name for evaluation in evaluations) == ("alpha", "zeta")
    assert evaluations[0].signal.direction is SignalDirection.BUY
    assert evaluations[1].signal.direction is SignalDirection.HOLD
    assert all(evaluation.signal_ref is None for evaluation in evaluations)


def test_threshold_strategy_emits_buy_sell_or_hold_deterministically() -> None:
    strategy = _strategy("threshold")

    buy = strategy.evaluate(_context(prediction=_prediction(probability_up=Decimal("0.75"))))
    sell = strategy.evaluate(_context(prediction=_prediction(probability_up=Decimal("0.20"))))
    hold = strategy.evaluate(_context(prediction=_prediction(probability_up=Decimal("0.55"))))

    assert buy.signal.direction is SignalDirection.BUY
    assert buy.plan.stop_suggestion is not None
    assert buy.plan.target_suggestion is not None
    assert sell.signal.direction is SignalDirection.SELL
    assert hold.signal.direction is SignalDirection.HOLD
    assert hold.plan.stop_suggestion is None
    assert hold.plan.target_suggestion is None


def test_disabled_strategy_emits_hold_without_order_or_risk_authority() -> None:
    registry = StrategyRegistry()
    registry.register(_strategy("disabled-at-registry"))
    registry.disable("disabled-at-registry")
    engine = StrategyEngine(
        registry,
        config=StrategyEngineConfig(
            include_disabled=True,
            persist_signals=False,
            audit_signals=False,
        ),
    )

    evaluation = engine.evaluate(
        "disabled-at-registry",
        _context(prediction=_prediction(probability_up=Decimal("0.80"))),
    )

    assert not evaluation.enabled
    assert evaluation.signal.direction is SignalDirection.HOLD
    assert evaluation.signal.confidence == Decimal("0")
    assert evaluation.reasons == ("strategy is disabled",)
    assert not hasattr(evaluation, "order_intent")
    assert not hasattr(evaluation, "risk_decision")
    assert not hasattr(evaluation, "exchange_order")


def test_bad_regime_or_prediction_blocks_directional_signal() -> None:
    strategy = _strategy("safety")
    shock_context = _context(
        prediction=_prediction(probability_up=Decimal("0.80")),
        return_1=Decimal("-0.09"),
    )
    shock_regime = MarketRegimeClassifier().classify(shock_context.features)
    non_actionable_prediction = _prediction(probability_up=Decimal("0.80"), actionable=False)

    blocked_by_regime = strategy.evaluate(
        StrategyContext(
            features=shock_context.features,
            generated_at=NOW,
            timeframe="1h",
            prediction=shock_context.prediction,
            regime=shock_regime,
        )
    )
    blocked_by_prediction = strategy.evaluate(_context(prediction=non_actionable_prediction))

    assert blocked_by_regime.signal.direction is SignalDirection.HOLD
    assert "regime risk context blocks new entries" in blocked_by_regime.reasons
    assert blocked_by_prediction.signal.direction is SignalDirection.HOLD
    assert "prediction is not actionable" in blocked_by_prediction.reasons


def test_engine_persists_signal_and_audit_event(migrated_connection: Connection) -> None:
    registry = build_registry((_strategy("audited"),))
    intelligence = IntelligenceRepository(migrated_connection)
    audits = AuditRepository(migrated_connection)
    engine = StrategyEngine(
        registry,
        intelligence_repository=intelligence,
        audit_repository=audits,
    )

    evaluation = engine.evaluate(
        "audited",
        _context(prediction=_prediction(probability_up=Decimal("0.80"))),
    )

    assert evaluation.signal_ref is not None
    assert evaluation.audit_event_id is not None
    stored_signal = intelligence.get_signal(evaluation.signal_ref)
    audit = audits.get(evaluation.audit_event_id)
    assert stored_signal == evaluation.signal
    assert audit is not None
    assert audit.payload["strategy_name"] == "audited"
    assert audit.payload["direction"] == SignalDirection.BUY.value


def _strategy(
    name: str,
    *,
    buy_threshold: Decimal = Decimal("0.60"),
    sell_threshold: Decimal = Decimal("0.60"),
    enabled: bool = True,
) -> ThresholdRuleStrategy:
    return ThresholdRuleStrategy(
        ThresholdRuleStrategyConfig(
            name=name,
            version="stage-020.test",
            enabled=enabled,
            buy_probability_threshold=buy_threshold,
            sell_probability_threshold=sell_threshold,
            minimum_confidence=Decimal("0.30"),
        )
    )


def _context(
    *,
    prediction: PredictionServiceResult,
    return_1: Decimal = Decimal("0.01"),
) -> StrategyContext:
    snapshot = _snapshot(return_1=return_1)
    return StrategyContext(
        features=snapshot,
        generated_at=NOW,
        timeframe="1h",
        prediction=prediction,
        regime=MarketRegimeClassifier().classify(snapshot),
    )


def _snapshot(*, return_1: Decimal = Decimal("0.01")) -> FeatureSnapshot:
    return FeatureSnapshot(
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        generated_at=NOW,
        schema_version=FEATURE_SCHEMA_VERSION,
        values={
            "market.close": Decimal("100"),
            "market.return_1": return_1,
            "market.return_3": Decimal("0.02"),
            "market.volume_ratio": Decimal("1.0"),
            "indicator.sma.sma": Decimal("100"),
            "indicator.rsi.rsi": Decimal("58"),
            "indicator.atr.atr_pct": Decimal("0.010"),
            "data_quality.flag_count": Decimal("0"),
            "liquidity.spread_bps": Decimal("10"),
        },
        quality=_trusted_quality(),
        lookback_start=NOW - timedelta(hours=4),
        lookback_end=NOW,
        source_refs={"candles": "fixture:candles:strategy"},
    )


def _prediction(
    *,
    probability_up: Decimal,
    confidence: Decimal = Decimal("0.40"),
    actionable: bool = True,
) -> PredictionServiceResult:
    snapshot = _snapshot()
    probability_down = Decimal("1") - probability_up
    prediction_quality = (
        _trusted_quality()
        if actionable
        else DataQualityStatus(
            trust_level=DataTrustLevel.DEGRADED,
            issues=(
                DataQualityIssue(
                    flag="non_actionable_prediction",
                    severity=DataTrustLevel.DEGRADED,
                    reason="fixture non-actionable",
                ),
            ),
            source_ref="prediction:fixture",
            checked_at=NOW,
        )
    )
    baseline_prediction = BaselinePrediction(
        pair_symbol=snapshot.pair.symbol,
        generated_at=NOW,
        model_metadata=BaselineModelMetadata(
            model_name="fixture_model",
            version="stage-020.fixture",
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
        confidence=confidence,
        expected_return=Decimal("0.01"),
        expected_volatility=Decimal("0.02"),
        quality=prediction_quality,
        actionable=actionable,
        rationale="fixture prediction",
    )
    explanation = PredictionExplanation(
        model_name="fixture_model",
        model_version="stage-020.fixture",
        features_ref=snapshot.inputs_ref,
        summary="fixture explanation",
        feature_importance=(),
        data_quality_score=Decimal("1") if actionable else Decimal("0.4"),
        source_refs=snapshot.source_refs,
        generated_at=NOW,
        quality=prediction_quality,
        limitations=("fixture only",),
    )
    return PredictionServiceResult(
        prediction=baseline_prediction,
        explanation=explanation,
        actionable=actionable,
        non_actionable_reasons=() if actionable else ("fixture non-actionable",),
        generated_at=NOW,
        quality=prediction_quality,
        prediction_ref="fixture:prediction",
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:trusted",
        checked_at=NOW,
    )
