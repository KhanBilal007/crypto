"""Paper trading engine over live-like market data snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from abtp.ai import MarketRegimeClassifier, RegimeClassification
from abtp.data import (
    DataQualityIssue,
    DataQualityStatus,
    DataTrustLevel,
    LiveMarketDataUpdate,
    OrderBookMetrics,
    StreamHealth,
    normalize_timestamp,
)
from abtp.domain import (
    Candle,
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskCheck,
    RiskDecision,
    RiskDecisionStatus,
    Signal,
    SignalDirection,
)
from abtp.execution import ExecutionEngineConfig, ExecutionResult, PaperSafeExecutionEngine
from abtp.features import FEATURE_SCHEMA_VERSION, FeatureSnapshot
from abtp.indicators.volatility import atr
from abtp.paper.account import PaperAccountConfig, PaperTrade, PaperTradingAccount
from abtp.paper.simulator import (
    PaperFillSimulationConfig,
    build_paper_order_router,
    estimate_paper_fill,
)
from abtp.risk import RiskEngineConfig, RiskEvaluationRequest, RiskManagementEngine, RiskPolicy
from abtp.strategies import StrategyContext, StrategyEvaluation, StrategyPlugin, StrategySignalPlan


@dataclass(frozen=True, slots=True)
class PaperTradingConfig:
    """Paper trading cycle assumptions and safety controls."""

    timeframe: str
    order_quantity: Decimal = Decimal("0.01")
    fill_simulation: PaperFillSimulationConfig = PaperFillSimulationConfig()
    max_drawdown_halt_pct: Decimal = Decimal("0.10")
    block_degraded_data: bool = True
    minimum_history: int = 1
    allow_pyramiding: bool = True
    enforce_protective_exits: bool = True

    def __post_init__(self) -> None:
        if not self.timeframe.strip():
            raise ValueError("timeframe is required")
        if self.order_quantity <= Decimal("0"):
            raise ValueError("order_quantity must be positive")
        if self.minimum_history < 1:
            raise ValueError("minimum_history must be positive")
        if not Decimal("0") <= self.max_drawdown_halt_pct <= Decimal("1"):
            raise ValueError("max_drawdown_halt_pct must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class PaperMarketSnapshot:
    """Live-like market inputs for one paper trading decision cycle."""

    candle: Candle
    order_book_metrics: OrderBookMetrics
    health: StreamHealth
    received_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "received_at", normalize_timestamp(self.received_at))

    @classmethod
    def from_live_update(
        cls, update: LiveMarketDataUpdate, *, received_at: datetime
    ) -> PaperMarketSnapshot:
        """Build a paper snapshot from the read-only live stream update contract."""

        if update.candle is None:
            raise ValueError("paper trading requires a candle update")
        return cls(
            candle=update.candle,
            order_book_metrics=update.order_book_metrics,
            health=update.health,
            received_at=received_at,
        )


@dataclass(frozen=True, slots=True)
class PaperTradingCycleResult:
    """Auditable result of one paper trading decision cycle."""

    snapshot: PaperMarketSnapshot
    features: FeatureSnapshot
    regime: RegimeClassification
    strategy_evaluation: StrategyEvaluation | None
    risk_decision_status: str | None
    execution_result: ExecutionResult | None
    equity: Decimal
    skipped_reason: str | None = None

    @property
    def executed(self) -> bool:
        return self.execution_result is not None and self.execution_result.accepted


@dataclass(frozen=True, slots=True)
class PaperTradingState:
    """Current live-like paper performance state."""

    cycles: tuple[PaperTradingCycleResult, ...]
    trades: tuple[PaperTrade, ...]
    equity: Decimal
    total_fees: Decimal
    halted: bool


class PaperTradingEngine:
    """Run strategy, risk, and paper-safe execution against live-like data."""

    def __init__(
        self,
        *,
        strategy: StrategyPlugin,
        config: PaperTradingConfig,
        account: PaperTradingAccount | None = None,
        risk_policy: RiskPolicy | None = None,
    ) -> None:
        self._strategy = strategy
        self._config = config
        self._account = account or PaperTradingAccount(PaperAccountConfig())
        self._regime_classifier = MarketRegimeClassifier()
        self._risk_engine = RiskManagementEngine(
            policy=replace(risk_policy, fee_bps=config.fill_simulation.fee_bps)
            if risk_policy
            else RiskPolicy(
                fee_bps=config.fill_simulation.fee_bps,
                max_spread_bps=max(config.fill_simulation.spread_bps, Decimal("50")),
                max_slippage_bps=max(config.fill_simulation.slippage_bps, Decimal("25")),
            ),
            config=RiskEngineConfig(persist_decisions=False, audit_decisions=False),
        )
        self._execution_engine = PaperSafeExecutionEngine(
            router=build_paper_order_router(config.fill_simulation),
            config=ExecutionEngineConfig(persist_orders=False, audit_orders=False),
        )
        self._candles: list[Candle] = []
        self._cycles: list[PaperTradingCycleResult] = []
        self._halted = False
        self._stop_loss: Decimal | None = None
        self._take_profit: Decimal | None = None
        self._last_processed_at: datetime | None = None

    @property
    def strategy(self) -> StrategyPlugin:
        return self._strategy

    @property
    def last_processed_at(self) -> datetime | None:
        return self._last_processed_at

    def runtime_state(self) -> dict[str, str | bool | None]:
        """Persist exit levels and the candle cursor alongside the paper wallet."""
        return {
            "stop_loss": str(self._stop_loss) if self._stop_loss is not None else None,
            "take_profit": str(self._take_profit) if self._take_profit is not None else None,
            "last_processed_at": self._last_processed_at.isoformat()
            if self._last_processed_at
            else None,
            "halted": self._halted,
        }

    def restore_runtime_state(
        self,
        *,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
        last_processed_at: datetime | None,
        halted: bool = False,
    ) -> None:
        if any(
            value is not None and (not value.is_finite() or value <= 0)
            for value in (stop_loss, take_profit)
        ):
            raise ValueError("persisted protection prices must be finite and positive")
        self._stop_loss = stop_loss
        self._take_profit = take_profit
        self._last_processed_at = last_processed_at
        self._halted = halted

    @property
    def account(self) -> PaperTradingAccount:
        return self._account

    @property
    def cycles(self) -> tuple[PaperTradingCycleResult, ...]:
        return tuple(self._cycles)

    def state(self, *, mark_price: Decimal) -> PaperTradingState:
        """Return current paper performance state."""

        return PaperTradingState(
            cycles=self.cycles,
            trades=self.account.trades,
            equity=self.account.equity(mark_price),
            total_fees=self.account.state.fees_paid,
            halted=self._halted,
        )

    def on_market_update(
        self,
        update: LiveMarketDataUpdate | PaperMarketSnapshot,
        *,
        received_at: datetime | None = None,
        execute: bool = True,
        execution_reference_price: Decimal | None = None,
    ) -> PaperTradingCycleResult:
        """Process one live-like data update without real order execution."""

        snapshot = (
            PaperMarketSnapshot.from_live_update(
                update,
                received_at=received_at or datetime.now(UTC),
            )
            if isinstance(update, LiveMarketDataUpdate)
            else update
        )
        if snapshot.candle.closed_at > snapshot.received_at:
            raise ValueError("cannot process an unfinished candle")
        if self._candles and snapshot.candle.closed_at <= self._candles[-1].closed_at:
            if snapshot.candle == self._candles[-1] and self._cycles:
                return self._cycles[-1]
            raise ValueError("paper candles must be unique and chronological")
        self._candles.append(snapshot.candle)
        # Bound indicator work while retaining more than ten EMA-50 lookbacks.
        self._candles = self._candles[-600:]
        self._last_processed_at = snapshot.candle.closed_at
        features = self._build_feature_snapshot(snapshot)
        regime = self._regime_classifier.classify(features)
        skipped_reason = self._skip_reason(snapshot, features)
        if not execute:
            skipped_reason = "observation only; no historical or paused fills"
        elif len(self._candles) < self._config.minimum_history:
            skipped_reason = "indicator warmup"
        protection = (
            self._protective_exit(snapshot, features)
            if execute and not snapshot.health.is_stale and not snapshot.health.is_degraded
            else None
        )
        if protection is not None:
            evaluation, reference_price = protection
            execution_result, risk_status = self._maybe_execute(
                evaluation,
                snapshot,
                features,
                reference_price=reference_price,
            )
            if execution_result is not None:
                self.account.apply_execution(execution_result, mark_price=snapshot.candle.close)
                self._clear_closed_protection()
            return self._record_cycle(
                PaperTradingCycleResult(
                    snapshot=snapshot,
                    features=features,
                    regime=regime,
                    strategy_evaluation=evaluation,
                    risk_decision_status=risk_status,
                    execution_result=execution_result,
                    equity=self.account.equity(snapshot.candle.close),
                )
            )
        if skipped_reason is not None:
            self.account.mark_to_market(snapshot.candle.close)
            return self._record_cycle(
                PaperTradingCycleResult(
                    snapshot=snapshot,
                    features=features,
                    regime=regime,
                    strategy_evaluation=None,
                    risk_decision_status=None,
                    execution_result=None,
                    equity=self.account.equity(snapshot.candle.close),
                    skipped_reason=skipped_reason,
                )
            )
        context = StrategyContext(
            features=features,
            generated_at=snapshot.received_at,
            timeframe=self._config.timeframe,
            regime=regime,
        )
        evaluation = self._strategy.evaluate(context)
        execution_result, risk_status = self._maybe_execute(
            evaluation,
            snapshot,
            features,
            reference_price=execution_reference_price,
        )
        if execution_result is not None:
            self.account.apply_execution(execution_result, mark_price=snapshot.candle.close)
            if execution_result.accepted and evaluation.signal.direction is SignalDirection.BUY:
                self._stop_loss = evaluation.plan.stop_suggestion
                self._take_profit = evaluation.plan.target_suggestion
            self._clear_closed_protection()
        else:
            self.account.mark_to_market(snapshot.candle.close)
        return self._record_cycle(
            PaperTradingCycleResult(
                snapshot=snapshot,
                features=features,
                regime=regime,
                strategy_evaluation=evaluation,
                risk_decision_status=risk_status,
                execution_result=execution_result,
                equity=self.account.equity(snapshot.candle.close),
            )
        )

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject direct order submission; paper cycles must pass strategy and risk."""

        raise ValueError("paper trading orders must be created by risk-approved engine cycles")

    def _skip_reason(
        self,
        snapshot: PaperMarketSnapshot,
        features: FeatureSnapshot,
    ) -> str | None:
        if self._halted:
            return "paper risk halt active"
        if snapshot.health.is_stale:
            return "live data is stale"
        if self._config.block_degraded_data and snapshot.health.is_degraded:
            return "live data is degraded"
        if not features.quality.is_trusted:
            return "feature quality is not trusted"
        if (
            self.account.current_drawdown_pct(snapshot.candle.close)
            > self._config.max_drawdown_halt_pct
        ):
            self._halted = True
            return "paper drawdown halt active"
        return None

    def _maybe_execute(
        self,
        evaluation: StrategyEvaluation,
        snapshot: PaperMarketSnapshot,
        features: FeatureSnapshot,
        *,
        reference_price: Decimal | None = None,
    ) -> tuple[ExecutionResult | None, str | None]:
        if not evaluation.is_trade_signal:
            return None, None
        order_side = (
            OrderSide.BUY
            if evaluation.signal.direction.value == OrderSide.BUY.value
            else OrderSide.SELL
        )
        if order_side is OrderSide.SELL and self.account.state.base_quantity <= Decimal("0"):
            return None, "no_position_to_sell"
        if (
            order_side is OrderSide.BUY
            and not self._config.allow_pyramiding
            and self.account.state.base_quantity > 0
        ):
            return None, "existing_position"
        execution_price = reference_price if reference_price is not None else snapshot.candle.close
        estimate = estimate_paper_fill(
            reference_price=execution_price,
            side=order_side,
            config=self._config.fill_simulation,
        )
        proposed_order_id = uuid4()
        if order_side is OrderSide.SELL:
            quantity = self.account.state.base_quantity
            risk_decision = RiskDecision(
                order_intent_id=proposed_order_id,
                status=RiskDecisionStatus.APPROVED,
                checks=(
                    RiskCheck(
                        name="paper_exit_reduces_exposure",
                        passed=True,
                        reason="paper sell exit reduces or closes simulated BTC exposure",
                    ),
                ),
                evaluated_at=snapshot.received_at,
                policy_version="paper-exit.v1",
                rationale="Paper sell exit approved because it reduces simulated exposure.",
                max_position_size=quantity,
                stop_loss_required=False,
            )
            intent = OrderIntent(
                id=proposed_order_id,
                pair=snapshot.candle.pair,
                side=order_side,
                order_type=OrderType.MARKET,
                quantity=quantity,
                created_at=snapshot.received_at,
                signal=evaluation.signal,
                risk_decision=risk_decision,
                status=OrderStatus.RISK_APPROVED,
                client_order_ref=f"paper-{proposed_order_id}",
            )
            return (
                self._execution_engine.submit(
                    intent,
                    idempotency_key=f"paper:{proposed_order_id}",
                    submitted_at=snapshot.received_at,
                    execution_price=execution_price,
                ),
                "approved_exit",
            )
        risk_decision = self._risk_engine.evaluate(
            RiskEvaluationRequest(
                strategy_evaluation=evaluation,
                portfolio=self.account.risk_context(
                    price=snapshot.candle.close,
                    checked_at=snapshot.received_at,
                    data_quality=features.quality,
                ),
                evaluated_at=snapshot.received_at,
                proposed_order_id=proposed_order_id,
                entry_price=estimate.execution_price,
                spread_bps=self._config.fill_simulation.spread_bps,
                estimated_slippage_bps=self._config.fill_simulation.slippage_bps,
            )
        )
        if not risk_decision.allowed:
            return None, risk_decision.status.value
        intent = OrderIntent(
            id=proposed_order_id,
            pair=snapshot.candle.pair,
            side=order_side,
            order_type=OrderType.MARKET,
            quantity=min(self._config.order_quantity, risk_decision.max_position_size),
            created_at=snapshot.received_at,
            signal=evaluation.signal,
            risk_decision=risk_decision,
            status=OrderStatus.RISK_APPROVED,
            client_order_ref=f"paper-{proposed_order_id}",
        )
        return (
            self._execution_engine.submit(
                intent,
                idempotency_key=f"paper:{proposed_order_id}",
                submitted_at=snapshot.received_at,
                execution_price=execution_price,
            ),
            risk_decision.status.value,
        )

    def _clear_closed_protection(self) -> None:
        if self.account.state.base_quantity == 0:
            self._stop_loss = None
            self._take_profit = None

    def _protective_exit(
        self,
        snapshot: PaperMarketSnapshot,
        features: FeatureSnapshot,
    ) -> tuple[StrategyEvaluation, Decimal] | None:
        if not self._config.enforce_protective_exits or self.account.state.base_quantity <= 0:
            return None
        candle = snapshot.candle
        # If both levels were crossed, assume the stop happened first. Gaps fill worse.
        if self._stop_loss is not None and candle.low <= self._stop_loss:
            reason = "protective stop-loss triggered"
            price = min(candle.open, self._stop_loss)
        elif self._take_profit is not None and candle.high >= self._take_profit:
            reason = "protective take-profit triggered"
            price = self._take_profit
        elif self._halted:
            reason = "drawdown halt closes existing exposure"
            price = candle.close
        else:
            return None
        config = self._strategy.config
        evaluation = StrategyEvaluation(
            strategy_name=config.name,
            strategy_version=config.version,
            enabled=True,
            signal=Signal(
                source=f"{config.name}:paper-protection",
                pair=candle.pair,
                generated_at=snapshot.received_at,
                direction=SignalDirection.SELL,
                confidence=Decimal("1"),
                inputs_ref=features.inputs_ref,
                rationale=reason,
            ),
            plan=StrategySignalPlan(
                entry_reason=reason,
                timeframe=self._config.timeframe,
                feature_snapshot_ref=features.inputs_ref,
            ),
            reasons=(reason,),
            generated_at=snapshot.received_at,
        )
        return evaluation, price

    def _build_feature_snapshot(self, snapshot: PaperMarketSnapshot) -> FeatureSnapshot:
        candles = tuple(self._candles)
        latest = candles[-1]
        previous = candles[-2] if len(candles) >= 2 else latest
        lookback = candles[-4] if len(candles) >= 4 else candles[0]
        sma_window = candles[-3:]
        previous_window = candles[:-1][-20:] if len(candles) > 1 else candles
        resistance_20 = max((candle.high for candle in previous_window), default=latest.high)
        support_20 = min((candle.low for candle in previous_window), default=latest.low)
        pullback_from_high_pct = (
            (resistance_20 - latest.close) / resistance_20
            if resistance_20 > Decimal("0") and latest.close < resistance_20
            else Decimal("0")
        )
        avg_volume = (
            sum((candle.volume for candle in previous_window), Decimal("0"))
            / Decimal(len(previous_window))
            if len(candles) > 1
            else latest.volume
        )
        spread_bps = (
            snapshot.order_book_metrics.spread / latest.close * Decimal("10000")
            if latest.close > Decimal("0")
            else Decimal("999999")
        )
        issues = _quality_issues(snapshot.health)
        trust_level = _trust_level(issues)
        values = {
            "market.close": latest.close,
            "market.return_1": latest.close / previous.close - Decimal("1")
            if previous.close
            else Decimal("0"),
            "market.return_3": latest.close / lookback.close - Decimal("1")
            if lookback.close
            else Decimal("0"),
            "market.volume_ratio": latest.volume / avg_volume if avg_volume else Decimal("1"),
            "market.support_20": support_20,
            "market.resistance_20": resistance_20,
            "market.pullback_from_high_pct": pullback_from_high_pct,
            "indicator.sma.sma": sum((candle.close for candle in sma_window), Decimal("0"))
            / Decimal(len(sma_window)),
            "indicator.ema_9": _ema(candles, period=9),
            "indicator.ema_21": _ema(candles, period=21),
            "indicator.ema_50": _ema(candles, period=50),
            "indicator.rsi.rsi": _rsi(candles, period=14),
            "indicator.atr.atr_pct": _atr_pct(candles, snapshot.received_at),
            "execution.round_trip_cost_pct": (
                self._config.fill_simulation.fee_bps * 2
                + self._config.fill_simulation.spread_bps
                + self._config.fill_simulation.slippage_bps * 2
            )
            / Decimal("10000"),
            "data_quality.flag_count": Decimal(len(issues)),
            "liquidity.spread_bps": spread_bps,
            "liquidity.imbalance": snapshot.order_book_metrics.imbalance,
            "liquidity.slippage_bps": self._config.fill_simulation.slippage_bps,
            "stream.latency_ms": Decimal(snapshot.health.latency_ms),
            "stream.disconnect_count": Decimal(snapshot.health.disconnect_count),
            "portfolio.exposure_base": self.account.state.base_quantity,
            "portfolio.cash_quote": self.account.state.cash,
        }
        return FeatureSnapshot(
            pair=latest.pair,
            generated_at=snapshot.received_at,
            schema_version=FEATURE_SCHEMA_VERSION,
            values=values,
            quality=DataQualityStatus(
                trust_level=trust_level,
                issues=issues,
                source_ref=f"paper:features:{latest.closed_at.isoformat()}",
                checked_at=snapshot.received_at,
            ),
            lookback_start=candles[0].opened_at,
            lookback_end=latest.closed_at,
            source_refs={
                "candles": f"paper:candles:{len(candles)}",
                "stream": snapshot.health.status,
            },
        )

    def _record_cycle(self, result: PaperTradingCycleResult) -> PaperTradingCycleResult:
        self._cycles.append(result)
        return result


def _quality_issues(health: StreamHealth) -> tuple[DataQualityIssue, ...]:
    issues: list[DataQualityIssue] = []
    if health.is_stale:
        issues.append(
            DataQualityIssue(
                flag="stale_live_data",
                severity=DataTrustLevel.REJECTED,
                reason="paper cycle received stale live data",
            )
        )
    elif health.is_degraded:
        issues.append(
            DataQualityIssue(
                flag="degraded_live_data",
                severity=DataTrustLevel.DEGRADED,
                reason="paper cycle received degraded live data",
            )
        )
    return tuple(issues)


def _trust_level(issues: tuple[DataQualityIssue, ...]) -> DataTrustLevel:
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        return DataTrustLevel.REJECTED
    if issues:
        return DataTrustLevel.DEGRADED
    return DataTrustLevel.TRUSTED


def _ema(candles: tuple[Candle, ...], *, period: int) -> Decimal:
    if not candles:
        return Decimal("0")
    closes = tuple(candle.close for candle in candles)
    multiplier = Decimal("2") / Decimal(period + 1)
    value = closes[0]
    for close in closes[1:]:
        value = close * multiplier + value * (Decimal("1") - multiplier)
    return value


def _rsi(candles: tuple[Candle, ...], *, period: int) -> Decimal:
    if len(candles) < 2:
        return Decimal("50")
    if len(candles) < period + 1:
        return Decimal("58") if candles[-1].close >= candles[0].close else Decimal("45")
    closes = tuple(candle.close for candle in candles[-(period + 1) :])
    changes = tuple(closes[index] - closes[index - 1] for index in range(1, len(closes)))
    if not changes:
        return Decimal("50")
    gains = tuple(max(change, Decimal("0")) for change in changes)
    losses = tuple(abs(min(change, Decimal("0"))) for change in changes)
    average_gain = sum(gains, Decimal("0")) / Decimal(len(gains))
    average_loss = sum(losses, Decimal("0")) / Decimal(len(losses))
    if average_gain == 0 and average_loss == 0:
        return Decimal("50")
    if average_loss == Decimal("0"):
        return Decimal("100")
    relative_strength = average_gain / average_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))


def _atr_pct(candles: tuple[Candle, ...], calculated_at: datetime) -> Decimal:
    if len(candles) < 2:
        return (candles[-1].high - candles[-1].low) / candles[-1].close
    result = atr(candles, calculated_at=calculated_at, period=min(14, len(candles) - 1))
    return result.values["atr"] / candles[-1].close
