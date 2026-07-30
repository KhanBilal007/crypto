from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from abtp.domain import (
    Asset,
    AssetPair,
    Exchange,
    FeatureVector,
    OrderBookLevel,
    OrderBookSnapshot,
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    PortfolioSnapshot,
    Prediction,
    PredictionHorizon,
    RiskCheck,
    RiskDecision,
    RiskDecisionStatus,
    Signal,
    SignalDirection,
)
from abtp.interfaces import (
    MarketDataProvider,
    OrderExecutionGateway,
    PortfolioRepository,
    PredictionEngine,
    RiskManagementEngine,
    StrategyEngine,
)

PAIR = AssetPair(Asset("BTC"), Asset("USDT"))
EXCHANGE = Exchange("fixture")
NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FixtureMarketDataProvider:
    def candles(self, pair: AssetPair, interval: str, start: datetime, end: datetime) -> tuple:
        return ()

    def order_book(self, pair: AssetPair) -> OrderBookSnapshot:
        level = OrderBookLevel(Decimal("100"), Decimal("1"))
        return OrderBookSnapshot(EXCHANGE, pair, NOW, (level,), (level,), "fixture:book")

    def trades(self, pair: AssetPair, start: datetime, end: datetime) -> tuple:
        return ()


class FixturePredictionEngine:
    def predict(self, features: FeatureVector) -> Prediction:
        return Prediction(
            pair=features.pair,
            generated_at=features.generated_at,
            horizon=PredictionHorizon.INTRADAY,
            expected_return=Decimal("0.01"),
            confidence=Decimal("0.7"),
            model_version="fixture-model",
            features_ref=features.inputs_ref,
            rationale="Fixture prediction.",
        )


class FixtureStrategyEngine:
    def generate_signal(
        self, features: FeatureVector, prediction: Prediction | None = None
    ) -> Signal:
        return Signal(
            source="fixture-strategy",
            pair=features.pair,
            generated_at=features.generated_at,
            direction=SignalDirection.HOLD,
            confidence=Decimal("0.5"),
            inputs_ref=features.inputs_ref,
            rationale="Fixture signal.",
        )


class FixtureRiskEngine:
    def evaluate(self, intent: OrderIntent, portfolio: PortfolioSnapshot) -> RiskDecision:
        return RiskDecision(
            order_intent_id=intent.id,
            status=RiskDecisionStatus.REJECTED,
            checks=(RiskCheck("fixture", False, "no execution in interface test"),),
            evaluated_at=portfolio.captured_at,
            policy_version="fixture-risk",
            rationale="Fixture rejection.",
            kill_switch_active=True,
        )


class FixturePortfolioRepository:
    def snapshot(self, captured_at: datetime | None = None) -> PortfolioSnapshot:
        return PortfolioSnapshot(captured_at or NOW, (), "fixture:portfolio")


class FixtureExecutionGateway:
    def submit(self, intent: OrderIntent, risk_decision: RiskDecision) -> OrderStatus:
        return OrderStatus.RISK_REJECTED if risk_decision.rejected else OrderStatus.SUBMITTED


def test_fixture_classes_satisfy_protocol_interfaces() -> None:
    data_provider: MarketDataProvider = FixtureMarketDataProvider()
    prediction_engine: PredictionEngine = FixturePredictionEngine()
    strategy_engine: StrategyEngine = FixtureStrategyEngine()
    risk_engine: RiskManagementEngine = FixtureRiskEngine()
    portfolio_repo: PortfolioRepository = FixturePortfolioRepository()
    execution_gateway: OrderExecutionGateway = FixtureExecutionGateway()

    features = FeatureVector(PAIR, NOW, {"x": Decimal("1")}, "fixture:inputs", "v1")
    prediction = prediction_engine.predict(features)
    signal = strategy_engine.generate_signal(features, prediction)
    intent = OrderIntent(PAIR, OrderSide.BUY, OrderType.MARKET, Decimal("0.01"), NOW, signal)
    portfolio = portfolio_repo.snapshot(NOW)
    decision = risk_engine.evaluate(intent, portfolio)

    assert data_provider.order_book(PAIR).pair == PAIR
    assert prediction.pair == PAIR
    assert signal.inputs_ref == "fixture:inputs"
    assert decision.rejected is True
    assert execution_gateway.submit(intent, decision) is OrderStatus.RISK_REJECTED
