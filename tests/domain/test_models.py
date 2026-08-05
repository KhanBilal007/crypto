from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

import abtp
from abtp.domain import (
    Asset,
    AssetPair,
    AuditEvent,
    AuditEventType,
    Candle,
    Exchange,
    FeatureVector,
    MarketType,
    OrderBookLevel,
    OrderBookSnapshot,
    OrderIntent,
    OrderSide,
    OrderType,
    PortfolioPosition,
    PortfolioSnapshot,
    Prediction,
    PredictionHorizon,
    RiskCheck,
    RiskDecision,
    RiskDecisionStatus,
    Signal,
    SignalDirection,
    Trade,
)


def fixture_pair() -> AssetPair:
    return AssetPair(Asset("btc", "Bitcoin"), Asset("usdt", "Tether USD"))


def fixture_exchange() -> Exchange:
    return Exchange("fixture")


def fixture_signal() -> Signal:
    return Signal(
        source="fixture-strategy",
        pair=fixture_pair(),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        direction=SignalDirection.BUY,
        confidence=Decimal("0.80"),
        inputs_ref="fixture:features:1",
        rationale="Deterministic fixture signal.",
    )


def test_candle_serializes_to_json_compatible_values() -> None:
    candle = Candle(
        exchange=fixture_exchange(),
        pair=fixture_pair(),
        interval="1m",
        opened_at=datetime(2026, 1, 1, tzinfo=UTC),
        closed_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("2.5"),
    )

    payload = candle.to_json_dict()

    assert payload["close"] == "105"
    assert payload["pair"] == {
        "base": {"symbol": "BTC", "name": "Bitcoin"},
        "quote": {"symbol": "USDT", "name": "Tether USD"},
    }
    assert payload["exchange"] == {"name": "fixture", "market_types": ["spot"]}
    assert Candle.from_json_dict(payload) == candle


def test_market_type_rejects_non_spot_exchange_for_current_stage() -> None:
    with pytest.raises(ValueError, match="spot vocabulary only"):
        Exchange("fixture", frozenset({MarketType.FUTURES}))


def test_market_data_models_validate_positive_values() -> None:
    with pytest.raises(ValueError, match="order book price must be positive"):
        OrderBookLevel(price=Decimal("0"), quantity=Decimal("1"))

    with pytest.raises(ValueError, match="trade quantity must be positive"):
        Trade(
            exchange=fixture_exchange(),
            pair=fixture_pair(),
            traded_at=datetime(2026, 1, 1, tzinfo=UTC),
            price=Decimal("1"),
            quantity=Decimal("0"),
            side=OrderSide.BUY,
            trade_id="t-1",
        )


def test_order_book_snapshot_requires_two_sides() -> None:
    with pytest.raises(ValueError, match="at least one bid and one ask"):
        OrderBookSnapshot(
            exchange=fixture_exchange(),
            pair=fixture_pair(),
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
            bids=(),
            asks=(OrderBookLevel(Decimal("101"), Decimal("1")),),
            source_ref="fixture:book:1",
        )


def test_feature_prediction_and_signal_are_explainable() -> None:
    features = FeatureVector(
        pair=fixture_pair(),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        values={"return_1m": Decimal("0.01")},
        inputs_ref="fixture:candle:1",
        feature_version="features-v1",
    )
    prediction = Prediction(
        pair=features.pair,
        generated_at=features.generated_at,
        horizon=PredictionHorizon.INTRADAY,
        expected_return=Decimal("0.02"),
        confidence=Decimal("0.65"),
        model_version="model-v1",
        features_ref="fixture:features:1",
        rationale="Fixture prediction for contract tests.",
    )
    signal = Signal(
        source="fixture-strategy",
        pair=features.pair,
        generated_at=features.generated_at,
        direction=SignalDirection.BUY,
        confidence=Decimal("0.70"),
        inputs_ref="fixture:prediction:1",
        rationale="Fixture signal from prediction.",
        prediction_ref="fixture:prediction:1",
    )

    assert features.to_json_dict()["values"] == {"return_1m": "0.01"}
    assert prediction.to_json_dict()["horizon"] == "intraday"
    assert signal.to_json_dict()["prediction_ref"] == "fixture:prediction:1"


def test_risk_decision_contains_required_minimum_controls() -> None:
    order_id = UUID("00000000-0000-0000-0000-000000000007")
    decision = RiskDecision(
        order_intent_id=order_id,
        status=RiskDecisionStatus.REJECTED,
        checks=(RiskCheck("max-position", False, "position limit exceeded"),),
        evaluated_at=datetime(2026, 1, 1, tzinfo=UTC),
        policy_version="risk-v1",
        rationale="Reject fixture order.",
        max_position_size=Decimal("0.05"),
        stop_loss_required=True,
        kill_switch_active=False,
    )

    payload = decision.to_json_dict()

    assert decision.allowed is False
    assert decision.rejected is True
    assert payload["allow"] is False
    assert payload["reject"] is True
    assert payload["reasons"] == ["position limit exceeded"]
    assert payload["max_position_size"] == "0.05"
    assert payload["stop_loss_required"] is True
    assert payload["kill_switch_active"] is False


def test_risk_decision_rejects_inconsistent_approval() -> None:
    with pytest.raises(ValueError, match="all checks to pass"):
        RiskDecision(
            order_intent_id=UUID("00000000-0000-0000-0000-000000000008"),
            status=RiskDecisionStatus.APPROVED,
            checks=(RiskCheck("fixture", False, "failed"),),
            evaluated_at=datetime(2026, 1, 1, tzinfo=UTC),
            policy_version="risk-v1",
            rationale="Should fail.",
        )


def test_order_intent_links_to_matching_risk_decision() -> None:
    signal = fixture_signal()
    intent = OrderIntent(
        pair=signal.pair,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.01"),
        limit_price=Decimal("100"),
        created_at=signal.generated_at,
        signal=signal,
    )
    decision = RiskDecision(
        order_intent_id=intent.id,
        status=RiskDecisionStatus.APPROVED,
        checks=(RiskCheck("fixture", True, "passed"),),
        evaluated_at=signal.generated_at,
        policy_version="risk-v1",
        rationale="Approved fixture.",
        max_position_size=Decimal("0.02"),
    )

    approved_intent = OrderIntent(
        id=intent.id,
        pair=intent.pair,
        side=intent.side,
        order_type=intent.order_type,
        quantity=intent.quantity,
        limit_price=intent.limit_price,
        created_at=intent.created_at,
        signal=intent.signal,
        risk_decision=decision,
    )

    assert approved_intent.risk_decision == decision


def test_portfolio_and_audit_models_serialize_for_audit_logging() -> None:
    snapshot = PortfolioSnapshot(
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        positions=(
            PortfolioPosition(
                asset=Asset("btc"),
                quantity=Decimal("0.25"),
                valuation_quote=Asset("usdt"),
                valuation=Decimal("25000"),
            ),
        ),
        source_ref="fixture:portfolio:1",
    )
    event = AuditEvent(
        event_type=AuditEventType.PORTFOLIO_SNAPSHOT,
        occurred_at=snapshot.captured_at,
        payload={"snapshot_ref": snapshot.source_ref},
    )

    assert snapshot.to_json_dict()["positions"][0]["quantity"] == "0.25"
    assert event.to_json_dict()["event_type"] == "portfolio_snapshot"


def test_backward_compatible_public_imports_use_domain_models() -> None:
    assert abtp.TradingPair is AssetPair
    assert abtp.Candle is Candle
    assert abtp.RiskDecision is RiskDecision
