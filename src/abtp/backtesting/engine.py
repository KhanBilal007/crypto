"""Historical backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from abtp.ai import MarketRegimeClassifier
from abtp.backtesting.broker import BacktestBroker, BacktestBrokerConfig, BacktestTrade
from abtp.backtesting.slippage import (
    SlippageModelConfig,
    estimate_execution_price,
)
from abtp.data import DataQualityStatus, DataTrustLevel
from abtp.domain import Candle, OrderIntent, OrderSide, OrderStatus, OrderType
from abtp.execution import (
    ExecutionEngineConfig,
    ExecutionResult,
    OrderRouterConfig,
    PaperOrderRouter,
    PaperSafeExecutionEngine,
)
from abtp.features import FEATURE_SCHEMA_VERSION, FeatureSnapshot
from abtp.risk import RiskEngineConfig, RiskEvaluationRequest, RiskManagementEngine, RiskPolicy
from abtp.strategies import StrategyContext, StrategyEvaluation, StrategyPlugin


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Backtest simulation assumptions."""

    timeframe: str
    initial_cash: Decimal = Decimal("10000")
    order_quantity: Decimal = Decimal("0.01")
    slippage: SlippageModelConfig = SlippageModelConfig()
    max_drawdown_halt_pct: Decimal = Decimal("0.15")

    def __post_init__(self) -> None:
        if not self.timeframe.strip():
            raise ValueError("timeframe is required")
        if self.initial_cash <= Decimal("0"):
            raise ValueError("initial_cash must be positive")
        if self.order_quantity <= Decimal("0"):
            raise ValueError("order_quantity must be positive")
        if not Decimal("0") <= self.max_drawdown_halt_pct <= Decimal("1"):
            raise ValueError("max_drawdown_halt_pct must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class BacktestStepResult:
    """One candle replay step with audit-oriented artifacts."""

    candle: Candle
    features: FeatureSnapshot
    strategy_evaluation: StrategyEvaluation
    risk_decision_status: str | None
    execution_result: ExecutionResult | None
    equity: Decimal
    skipped_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Complete deterministic backtest result."""

    steps: tuple[BacktestStepResult, ...]
    trades: tuple[BacktestTrade, ...]
    starting_equity: Decimal
    ending_equity: Decimal
    net_return: Decimal
    max_drawdown: Decimal
    total_fees: Decimal
    costs_included: bool

    @property
    def risk_decision_count(self) -> int:
        return sum(1 for step in self.steps if step.risk_decision_status is not None)


@dataclass(frozen=True, slots=True)
class _ExecutionAttempt:
    risk_decision_status: str
    execution_result: ExecutionResult | None


class BacktestingEngine:
    """Replay historical candles through strategy, risk, and paper execution."""

    def __init__(
        self,
        *,
        strategy: StrategyPlugin,
        config: BacktestConfig,
        risk_policy: RiskPolicy | None = None,
    ) -> None:
        self._strategy = strategy
        self._config = config
        self._broker = BacktestBroker(BacktestBrokerConfig(initial_cash=config.initial_cash))
        self._regime_classifier = MarketRegimeClassifier()
        self._risk_engine = RiskManagementEngine(
            policy=risk_policy
            or RiskPolicy(
                fee_bps=config.slippage.fee_bps,
                max_slippage_bps=max(config.slippage.slippage_bps, Decimal("25")),
                max_spread_bps=max(config.slippage.spread_bps, Decimal("50")),
            ),
            config=RiskEngineConfig(persist_decisions=False, audit_decisions=False),
        )
        self._execution_engine = PaperSafeExecutionEngine(
            router=PaperOrderRouter(
                config=OrderRouterConfig(
                    fee_bps=config.slippage.fee_bps,
                    price_adjustment_bps=(
                        config.slippage.spread_bps / Decimal("2") + config.slippage.slippage_bps
                    ),
                )
            ),
            config=ExecutionEngineConfig(persist_orders=False, audit_orders=False),
        )

    @property
    def broker(self) -> BacktestBroker:
        return self._broker

    def run(self, candles: tuple[Candle, ...]) -> BacktestResult:
        """Replay candles in timestamp order with no lookahead features."""

        if not candles:
            raise ValueError("backtest requires candles")
        ordered = tuple(sorted(candles, key=lambda candle: candle.opened_at))
        steps: list[BacktestStepResult] = []
        for index, candle in enumerate(ordered):
            features = self.build_feature_snapshot(
                ordered[: index + 1], generated_at=candle.closed_at
            )
            regime = self._regime_classifier.classify(features)
            context = StrategyContext(
                features=features,
                generated_at=candle.closed_at,
                timeframe=self._config.timeframe,
                regime=regime,
            )
            evaluation = self._strategy.evaluate(context)
            if self._broker.current_drawdown_pct(candle.close) > self._config.max_drawdown_halt_pct:
                self._broker.mark_to_market(candle.close)
                steps.append(
                    BacktestStepResult(
                        candle=candle,
                        features=features,
                        strategy_evaluation=evaluation,
                        risk_decision_status=None,
                        execution_result=None,
                        equity=self._broker.equity(candle.close),
                        skipped_reason="drawdown halt active",
                    )
                )
                continue
            attempt = self._maybe_execute(evaluation, candle)
            if attempt is not None and attempt.execution_result is not None:
                self._broker.apply_execution(attempt.execution_result, mark_price=candle.close)
            else:
                self._broker.mark_to_market(candle.close)
            steps.append(
                BacktestStepResult(
                    candle=candle,
                    features=features,
                    strategy_evaluation=evaluation,
                    risk_decision_status=(
                        attempt.risk_decision_status if attempt is not None else None
                    ),
                    execution_result=attempt.execution_result if attempt is not None else None,
                    equity=self._broker.equity(candle.close),
                )
            )
        ending_equity = self._broker.equity(ordered[-1].close)
        return BacktestResult(
            steps=tuple(steps),
            trades=self._broker.trades,
            starting_equity=self._config.initial_cash,
            ending_equity=ending_equity,
            net_return=ending_equity / self._config.initial_cash - Decimal("1"),
            max_drawdown=self._broker.current_drawdown_pct(ordered[-1].close),
            total_fees=self._broker.account.fees_paid,
            costs_included=True,
        )

    def build_feature_snapshot(
        self,
        candles_so_far: tuple[Candle, ...],
        *,
        generated_at: datetime,
    ) -> FeatureSnapshot:
        """Build current-only features from candles available at this step."""

        if not candles_so_far:
            raise ValueError("candles_so_far is required")
        latest = candles_so_far[-1]
        previous = candles_so_far[-2] if len(candles_so_far) >= 2 else latest
        lookback = candles_so_far[-4] if len(candles_so_far) >= 4 else candles_so_far[0]
        sma_window = candles_so_far[-3:]
        avg_volume = (
            sum((candle.volume for candle in candles_so_far[:-1]), Decimal("0"))
            / Decimal(len(candles_so_far[:-1]))
            if len(candles_so_far) > 1
            else latest.volume
        )
        return_1 = latest.close / previous.close - Decimal("1") if previous.close else Decimal("0")
        return_3 = latest.close / lookback.close - Decimal("1") if lookback.close else Decimal("0")
        atr_pct = (latest.high - latest.low) / latest.close
        rsi = Decimal("58") if return_3 > Decimal("0") else Decimal("45")
        values = {
            "market.close": latest.close,
            "market.return_1": return_1,
            "market.return_3": return_3,
            "market.volume_ratio": latest.volume / avg_volume if avg_volume else Decimal("1"),
            "indicator.sma.sma": sum((candle.close for candle in sma_window), Decimal("0"))
            / Decimal(len(sma_window)),
            "indicator.rsi.rsi": rsi,
            "indicator.atr.atr_pct": atr_pct,
            "data_quality.flag_count": Decimal("0"),
            "liquidity.spread_bps": self._config.slippage.spread_bps,
        }
        return FeatureSnapshot(
            pair=latest.pair,
            generated_at=generated_at,
            schema_version=FEATURE_SCHEMA_VERSION,
            values=values,
            quality=DataQualityStatus(
                trust_level=DataTrustLevel.TRUSTED,
                issues=(),
                source_ref=f"backtest:features:{latest.closed_at.isoformat()}",
                checked_at=generated_at,
            ),
            lookback_start=candles_so_far[0].opened_at,
            lookback_end=latest.closed_at,
            source_refs={"candles": f"backtest:candles:{len(candles_so_far)}"},
        )

    def _maybe_execute(
        self,
        evaluation: StrategyEvaluation,
        candle: Candle,
    ) -> _ExecutionAttempt | None:
        if not evaluation.is_trade_signal:
            return None
        entry_price = estimate_execution_price(
            reference_price=candle.close,
            side=OrderSide.BUY,
            config=self._config.slippage,
        )
        proposed_order_id = uuid4()
        risk_decision = self._risk_engine.evaluate(
            RiskEvaluationRequest(
                strategy_evaluation=evaluation,
                portfolio=self._broker.risk_context(
                    price=candle.close, checked_at=candle.closed_at
                ),
                evaluated_at=candle.closed_at,
                proposed_order_id=proposed_order_id,
                entry_price=entry_price,
                spread_bps=self._config.slippage.spread_bps,
                estimated_slippage_bps=self._config.slippage.slippage_bps,
            )
        )
        if not risk_decision.allowed:
            return _ExecutionAttempt(
                risk_decision_status=risk_decision.status.value,
                execution_result=None,
            )
        intent = OrderIntent(
            id=proposed_order_id,
            pair=candle.pair,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=min(self._config.order_quantity, risk_decision.max_position_size),
            created_at=candle.closed_at,
            signal=evaluation.signal,
            risk_decision=risk_decision,
            status=(
                OrderStatus.RISK_APPROVED if risk_decision.allowed else OrderStatus.RISK_REJECTED
            ),
            client_order_ref=f"backtest-{proposed_order_id}",
        )
        return _ExecutionAttempt(
            risk_decision_status=risk_decision.status.value,
            execution_result=self._execution_engine.submit(
                intent,
                idempotency_key=f"backtest:{proposed_order_id}",
                submitted_at=candle.closed_at,
                execution_price=candle.close,
            ),
        )
