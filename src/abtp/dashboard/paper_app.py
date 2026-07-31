"""Paper-only local dashboard state and safe actions."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from sqlite3 import Connection
from uuid import UUID

from abtp.api import PaperAPIRequestContext, PaperAPIRole, PaperStatusResponse, PaperTradingAPI
from abtp.data import OrderBookMetrics, StreamHealth, calculate_order_book_metrics
from abtp.db import apply_migrations, connect_database
from abtp.domain import Asset, AssetPair, Candle, Exchange, OrderSide, Signal, SignalDirection
from abtp.domain.models import JsonValue
from abtp.exchanges import BinanceSpotMarketDataAdapter, ExchangeAdapterError
from abtp.paper import (
    PaperAccountConfig,
    PaperAccountState,
    PaperTrade,
    PaperTradingAccount,
    PaperTradingConfig,
    PaperTradingEngine,
)
from abtp.paper.engine import PaperMarketSnapshot, PaperTradingCycleResult
from abtp.repositories import PaperDashboardRepository
from abtp.risk import RiskPolicy
from abtp.strategies import (
    MinRiskSpotStrategyV1,
    StrategyConfig,
    StrategyContext,
    StrategyEvaluation,
    StrategyPlugin,
    StrategySignalPlan,
)

DECIMAL_ZERO = Decimal("0")
DEFAULT_NOW = datetime(2026, 1, 1, tzinfo=UTC)
PAIR = AssetPair(Asset("BTC"), Asset("USDT"))
READ_CONTEXT = PaperAPIRequestContext("paper-dashboard", frozenset({PaperAPIRole.READ}))
CONTROL_CONTEXT = PaperAPIRequestContext(
    "paper-dashboard-operator",
    frozenset({PaperAPIRole.READ, PaperAPIRole.CONTROL}),
)


class DashboardAction(StrEnum):
    """Safe paper dashboard operator actions."""

    APPROVE_PAPER_TRADE = "approve_paper_trade"
    REJECT_RECOMMENDATION = "reject_recommendation"
    PAUSE_PAPER_BOT = "pause_paper_bot"
    RESUME_PAPER_BOT = "resume_paper_bot"
    EMERGENCY_STOP = "emergency_stop"
    RESET_EMERGENCY_STOP = "reset_emergency_stop"


class DashboardUIMode(StrEnum):
    """Role-aware dashboard shell modes."""

    BEGINNER = "beginner"
    ADVANCED_TRADER = "advanced_trader"
    STRATEGY_LAB = "strategy_lab"


class StrategyLabRunMode(StrEnum):
    """Strategy Lab evidence mode; separate from live trading permissions."""

    PAPER = "paper"
    BACKTEST = "backtest"


class PaperDashboardActionError(ValueError):
    """Raised when a dashboard action is not allowed in paper mode."""


@dataclass(frozen=True, slots=True)
class PaperDashboardEvent:
    """One operator/audit log entry for the local paper dashboard."""

    event_type: str
    message: str
    occurred_at: datetime
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError("event_type is required")
        if not self.message.strip():
            raise ValueError("event message is required")

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "event_type": self.event_type,
            "message": self.message,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class DailyTrendConfirmation:
    """Daily trend gate for paper entries."""

    allow_buy: bool
    confidence_boost: Decimal
    reason: str
    source_ref: str


class MultiTimeframePaperStrategy:
    """Require 1d trend confirmation before accepting 1h BUY entries."""

    def __init__(
        self,
        base_strategy: StrategyPlugin,
        daily_confirmation: DailyTrendConfirmation,
    ) -> None:
        self._base_strategy = base_strategy
        self._daily_confirmation = daily_confirmation

    @property
    def config(self) -> StrategyConfig:
        return self._base_strategy.config

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        evaluation = self._base_strategy.evaluate(context)
        if evaluation.signal.direction is not SignalDirection.BUY:
            return evaluation
        if self._daily_confirmation.allow_buy:
            return _boosted_evaluation(evaluation, self._daily_confirmation)
        return _daily_blocked_evaluation(evaluation, self._daily_confirmation)


@dataclass(slots=True)
class PaperDashboardController:
    """Local paper dashboard controller with no live execution authority."""

    engine: PaperTradingEngine
    api: PaperTradingAPI
    report_path: str = "docs/paper_trading_status_report.md"
    state_path: str | None = None
    db_path: str | None = None
    market_data_source: str = "demo"
    ui_mode: DashboardUIMode = DashboardUIMode.ADVANCED_TRADER
    strategy_lab_strategy: str = "min_risk_spot_v1"
    strategy_lab_symbol: str = "BTC/USDT"
    strategy_lab_timeframe: str = "1h"
    strategy_lab_run_mode: StrategyLabRunMode = StrategyLabRunMode.PAPER
    strategy_lab_parameter_profile: str = "default"
    events: list[PaperDashboardEvent] = field(default_factory=list)

    def state(self, *, ui_mode: DashboardUIMode | str | None = None) -> dict[str, JsonValue]:
        """Return a browser-safe dashboard state payload."""

        active_ui_mode = _ui_mode(ui_mode or self.ui_mode)
        status = self.api.status(READ_CONTEXT)
        latest = self.engine.cycles[-1] if self.engine.cycles else None
        suggested_trade = _suggested_trade(latest)
        can_approve = (
            latest is not None
            and latest.executed
            and latest.risk_decision_status == "approved"
            and not status.paused
            and not status.kill_switch_active
        )
        payload: dict[str, JsonValue] = {
            "mode": "PAPER MODE",
            "safe_mode": True,
            "live_trading_enabled": False,
            "ui_mode": active_ui_mode.value,
            "ui": {
                "mode": active_ui_mode.value,
                "available_modes": [
                    {"value": DashboardUIMode.BEGINNER.value, "label": "Beginner"},
                    {"value": DashboardUIMode.ADVANCED_TRADER.value, "label": "Advanced Trader"},
                    {"value": DashboardUIMode.STRATEGY_LAB.value, "label": "Strategy Lab"},
                ],
                "trading_mode": "paper",
                "live_trading_enabled": False,
            },
            "unsupported_markets": {
                "leverage": False,
                "margin": False,
                "futures": False,
                "options": False,
                "withdrawals": False,
                "transfers": False,
            },
            "market": {
                "symbol": "BTC/USDT",
                "source": self.market_data_source,
                "current_price": _str(status.current_btc_price),
                "spread": _str(_latest_spread(latest)),
                "data_freshness": status.data_health,
                "market_regime": status.active_regime,
                "updated_at": status.updated_at.isoformat(),
            },
            "strategy": _strategy_state(status, latest),
            "suggested_paper_trade": suggested_trade,
            "portfolio": {
                "starting_balance": "10000",
                "current_equity": str(status.portfolio.equity),
                "cash": str(status.portfolio.cash),
                "open_btc": str(status.portfolio.base_quantity),
                "realized_pnl": str(status.portfolio.realized_pnl),
                "unrealized_pnl": _unrealized_pnl(status),
                "drawdown": str(status.portfolio.drawdown_pct),
                "risk_halts": list(_risk_halts(status)),
            },
            "controls": {
                "can_approve_paper_trade": can_approve,
                "approval_block_reason": "approval available for risk-approved simulated trade"
                if can_approve
                else _approval_block_reason(status, latest),
                "paused": status.paused,
                "kill_switch_active": status.kill_switch_active,
                "approve_label": "Approve Paper Trade",
                "reject_label": "Reject Recommendation",
                "pause_label": "Pause Paper Bot",
                "resume_label": "Resume Paper Bot",
                "emergency_label": "Emergency Stop",
                "reset_emergency_label": "Reset Emergency Stop",
            },
            "logs": list(event.as_dict() for event in self.events),
            "transactions": _transaction_state(self.api.trades(READ_CONTEXT)),
            "daily_report": {
                "label": "Daily paper-trading report",
                "path": self.report_path,
                "url": "/paper-report",
            },
            "warning": (
                "Paper trading only. This dashboard is not financial advice and cannot "
                "place real exchange orders."
            ),
        }
        payload["views"] = _adaptive_view_sections(
            payload=payload,
            status=status,
            cycles=self.engine.cycles,
            latest=latest,
            can_approve=can_approve,
            strategy_lab_selection={
                "strategy": self.strategy_lab_strategy,
                "symbol": self.strategy_lab_symbol,
                "timeframe": self.strategy_lab_timeframe,
                "run_mode": self.strategy_lab_run_mode.value,
                "parameter_profile": self.strategy_lab_parameter_profile,
            },
        )
        payload["readiness"] = _dashboard_readiness_gate(
            payload=payload,
            cycles=self.engine.cycles,
            events=self.events,
            db_path=self.db_path,
            state_path=self.state_path,
        )
        return payload

    def set_ui_mode(self, mode: DashboardUIMode | str) -> dict[str, JsonValue]:
        """Persist the preferred dashboard shell mode without changing trading permissions."""

        self.ui_mode = _ui_mode(mode)
        _save_dashboard_preferences(self)
        return self.state()

    def set_strategy_lab_selection(
        self,
        *,
        strategy: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        run_mode: str | None = None,
        parameter_profile: str | None = None,
    ) -> dict[str, JsonValue]:
        """Persist Strategy Lab selection without changing paper/live permissions."""

        if strategy is not None:
            self.strategy_lab_strategy = str(_strategy_profile(strategy)["key"])
        if symbol is not None:
            self.strategy_lab_symbol = _strategy_lab_symbol(symbol)
        if timeframe is not None:
            self.strategy_lab_timeframe = _strategy_lab_timeframe(
                timeframe,
                self.strategy_lab_strategy,
            )
        if run_mode is not None:
            self.strategy_lab_run_mode = _strategy_lab_run_mode(run_mode)
        if parameter_profile is not None:
            self.strategy_lab_parameter_profile = _strategy_lab_parameter_profile(
                parameter_profile,
                self.strategy_lab_strategy,
            )
        _save_dashboard_preferences(self)
        return self.state()

    def approve_paper_trade(self, *, reason: str = "operator approved paper trade") -> None:
        """Approve and apply one simulated risk-approved paper trade only."""

        state = self.state()
        controls = _as_mapping(state["controls"])
        if controls.get("can_approve_paper_trade") is not True:
            raise PaperDashboardActionError(str(controls.get("approval_block_reason")))
        latest = self.engine.cycles[-1] if self.engine.cycles else None
        if latest is None or latest.execution_result is None:
            raise PaperDashboardActionError("no risk-approved simulated paper fill is available")
        self.engine.account.apply_execution(
            latest.execution_result,
            mark_price=latest.snapshot.candle.close,
        )
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type=DashboardAction.APPROVE_PAPER_TRADE.value,
                message="Operator approved and applied a simulated paper trade only.",
                reason=reason,
                occurred_at=_latest_time(self.engine),
            ),
        )
        _save_paper_account_state(self)

    def reject_recommendation(self, *, reason: str = "operator rejected recommendation") -> None:
        """Record operator rejection without mutating engine state."""

        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type=DashboardAction.REJECT_RECOMMENDATION.value,
                message="Operator rejected the current paper recommendation.",
                reason=reason,
                occurred_at=_latest_time(self.engine),
            ),
        )
        _save_paper_account_state(self)

    def pause(self, *, reason: str = "operator paused paper bot") -> None:
        self.api.pause(CONTROL_CONTEXT, reason=reason, updated_at=_latest_time(self.engine))
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type=DashboardAction.PAUSE_PAPER_BOT.value,
                message="Paper bot paused.",
                reason=reason,
                occurred_at=_latest_time(self.engine),
            ),
        )
        _save_paper_account_state(self)

    def resume(self, *, reason: str = "operator resumed paper bot") -> None:
        if self.api.control_state.kill_switch_active:
            self.events.insert(
                0,
                PaperDashboardEvent(
                    event_type="resume_blocked",
                    message="Resume ignored because emergency stop is active.",
                    reason="Use Reset Emergency Stop first.",
                    occurred_at=_latest_time(self.engine),
                ),
            )
            _save_paper_account_state(self)
            return
        self.api.resume(CONTROL_CONTEXT, reason=reason, updated_at=_latest_time(self.engine))
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type=DashboardAction.RESUME_PAPER_BOT.value,
                message="Paper bot resumed.",
                reason=reason,
                occurred_at=_latest_time(self.engine),
            ),
        )
        _save_paper_account_state(self)

    def emergency_stop(self, *, reason: str = "operator emergency stop") -> None:
        self.api.activate_kill_switch(
            CONTROL_CONTEXT, reason=reason, updated_at=_latest_time(self.engine)
        )
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type=DashboardAction.EMERGENCY_STOP.value,
                message="Paper emergency stop activated.",
                reason=reason,
                occurred_at=_latest_time(self.engine),
            ),
        )
        _save_paper_account_state(self)

    def reset_emergency_stop(self, *, reason: str = "operator reset emergency stop") -> None:
        self.api.clear_kill_switch(
            CONTROL_CONTEXT, reason=reason, updated_at=_latest_time(self.engine)
        )
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type=DashboardAction.RESET_EMERGENCY_STOP.value,
                message="Paper emergency stop reset.",
                reason=reason,
                occurred_at=_latest_time(self.engine),
            ),
        )
        _save_paper_account_state(self)

    def create_live_order(self, *_args: object, **_kwargs: object) -> None:
        raise PaperDashboardActionError("paper dashboard cannot create live orders")

    def enable_live_trading(self, *_args: object, **_kwargs: object) -> None:
        raise PaperDashboardActionError("paper dashboard cannot enable live trading")


def build_default_paper_dashboard_controller(
    *,
    risk_policy: RiskPolicy | None = None,
    market_data_source: str | None = None,
    state_path: str | None = None,
    db_path: str | None = None,
) -> PaperDashboardController:
    """Create a deterministic local controller for dashboard development/testing."""

    source_name = (
        market_data_source
        if market_data_source is not None
        else os.getenv("ABTP_MARKET_DATA_SOURCE", "demo")
    )
    requested_market_source = source_name.strip().lower()
    snapshots, active_market_source, source_events, daily_confirmation = _dashboard_inputs(
        requested_market_source,
    )
    strategy: StrategyPlugin = MinRiskSpotStrategyV1()
    if daily_confirmation is not None:
        strategy = MultiTimeframePaperStrategy(strategy, daily_confirmation)
    engine = PaperTradingEngine(
        strategy=strategy,
        config=PaperTradingConfig(
            timeframe="1h",
            order_quantity=Decimal("0.01"),
            max_drawdown_halt_pct=Decimal("0.05"),
            block_degraded_data=True,
        ),
        account=PaperTradingAccount(PaperAccountConfig(initial_cash=Decimal("10000"))),
        risk_policy=risk_policy
        or RiskPolicy(
            max_risk_per_trade_pct=Decimal("0.0025"),
            max_daily_loss_pct=Decimal("0.01"),
            max_weekly_loss_pct=Decimal("0.03"),
            max_drawdown_pct=Decimal("0.05"),
            max_spread_bps=Decimal("25"),
            max_slippage_bps=Decimal("10"),
            require_stop_loss=True,
        ),
    )
    for snapshot in snapshots:
        engine.on_market_update(snapshot)
    controller = PaperDashboardController(
        engine=engine,
        api=PaperTradingAPI(engine),
        state_path=state_path if state_path is not None else os.getenv("ABTP_PAPER_STATE_PATH"),
        db_path=db_path if db_path is not None else os.getenv("ABTP_PAPER_DB_PATH"),
        market_data_source=active_market_source,
        events=[*source_events, *_initial_events(engine)],
    )
    _restore_paper_account_state(controller)
    return controller


def dispatch_dashboard_action(
    controller: PaperDashboardController,
    action: DashboardAction,
    *,
    reason: str = "",
) -> dict[str, JsonValue]:
    """Run a safe dashboard action and return the updated state."""

    active_reason = reason or f"{action.value} requested from paper dashboard"
    if action is DashboardAction.APPROVE_PAPER_TRADE:
        controller.approve_paper_trade(reason=active_reason)
    elif action is DashboardAction.REJECT_RECOMMENDATION:
        controller.reject_recommendation(reason=active_reason)
    elif action is DashboardAction.PAUSE_PAPER_BOT:
        controller.pause(reason=active_reason)
    elif action is DashboardAction.RESUME_PAPER_BOT:
        controller.resume(reason=active_reason)
    elif action is DashboardAction.EMERGENCY_STOP:
        controller.emergency_stop(reason=active_reason)
    elif action is DashboardAction.RESET_EMERGENCY_STOP:
        controller.reset_emergency_stop(reason=active_reason)
    return controller.state()


def _initial_events(engine: PaperTradingEngine) -> list[PaperDashboardEvent]:
    events: list[PaperDashboardEvent] = []
    for cycle in reversed(engine.cycles):
        if cycle.executed:
            events.append(
                PaperDashboardEvent(
                    event_type="paper_fill",
                    message="Simulated paper fill accepted after risk approval.",
                    reason=(cycle.execution_result.reason or "" if cycle.execution_result else ""),
                    occurred_at=cycle.snapshot.received_at,
                )
            )
        elif cycle.skipped_reason:
            events.append(
                PaperDashboardEvent(
                    event_type="stale_data_event"
                    if "stale" in cycle.skipped_reason
                    else "skipped_cycle",
                    message="Paper cycle skipped.",
                    reason=cycle.skipped_reason,
                    occurred_at=cycle.snapshot.received_at,
                )
            )
        elif cycle.strategy_evaluation is not None:
            events.append(
                PaperDashboardEvent(
                    event_type="latest_signal",
                    message=f"Strategy emitted {cycle.strategy_evaluation.signal.direction.value}.",
                    reason="; ".join(cycle.strategy_evaluation.reasons),
                    occurred_at=cycle.snapshot.received_at,
                )
            )
    events.append(
        PaperDashboardEvent(
            event_type="risk_rejection_reason",
            message="Risk rejection smoke is available for review.",
            reason="Risk Management Engine rejects kill-switch-active paper signals.",
            occurred_at=DEFAULT_NOW,
        )
    )
    events.append(
        PaperDashboardEvent(
            event_type="stale_data_event",
            message="Stale data event smoke is available for review.",
            reason="market snapshot is stale",
            occurred_at=DEFAULT_NOW,
        )
    )
    return events


def _dashboard_inputs(
    requested_market_source: str,
) -> tuple[
    tuple[PaperMarketSnapshot, ...],
    str,
    tuple[PaperDashboardEvent, ...],
    DailyTrendConfirmation | None,
]:
    if requested_market_source == "binance":
        try:
            snapshots, daily_confirmation = _binance_snapshots_and_daily_confirmation()
            return (
                snapshots,
                "binance spot",
                (
                    PaperDashboardEvent(
                        event_type="market_data_source",
                        message="Binance spot market data connected for paper trading.",
                        reason="market data only; real order placement remains disabled",
                        occurred_at=datetime.now(UTC),
                    ),
                ),
                daily_confirmation,
            )
        except (ExchangeAdapterError, OSError, ValueError) as exc:
            return (
                _demo_snapshots(),
                "demo fallback",
                (
                    PaperDashboardEvent(
                        event_type="market_data_source_fallback",
                        message="Demo market data loaded because Binance was unavailable.",
                        reason=str(exc),
                        occurred_at=datetime.now(UTC),
                    ),
                ),
                None,
            )
    return _demo_snapshots(), "demo", (), None


def _demo_snapshots() -> tuple[PaperMarketSnapshot, ...]:
    return tuple(
        _snapshot(index, Decimal(close)) for index, close in enumerate(("100", "101", "102", "104"))
    )


def _binance_snapshots_and_daily_confirmation() -> tuple[
    tuple[PaperMarketSnapshot, ...],
    DailyTrendConfirmation,
]:
    adapter = BinanceSpotMarketDataAdapter()
    order_book = adapter.order_book(PAIR)
    metrics = calculate_order_book_metrics(order_book)
    hourly_candles = adapter.candles(PAIR, "1h", 4)
    daily_confirmation = _daily_confirmation_from_candles(adapter.candles(PAIR, "1d", 4))
    snapshots = []
    for index, candle in enumerate(hourly_candles):
        snapshots.append(
            _snapshot(
                index,
                candle.close,
                exchange_name="binance",
                candle=candle,
                received_at=candle.closed_at + timedelta(milliseconds=1),
                order_book_metrics=metrics if index == len(hourly_candles) - 1 else None,
            )
        )
    return tuple(snapshots), daily_confirmation


def _daily_confirmation_from_candles(candles: tuple[Candle, ...]) -> DailyTrendConfirmation:
    if len(candles) < 4:
        return DailyTrendConfirmation(
            allow_buy=False,
            confidence_boost=Decimal("0"),
            reason="1d confirmation needs at least four closed candles",
            source_ref="binance:spot:1d:insufficient",
        )
    first = candles[0]
    latest = candles[-1]
    sma = sum((candle.close for candle in candles), Decimal("0")) / Decimal(len(candles))
    return_3d = (
        latest.close / first.close - Decimal("1") if first.close > DECIMAL_ZERO else DECIMAL_ZERO
    )
    allow_buy = latest.close > sma and return_3d >= Decimal("0.005")
    reason = (
        f"1d trend confirms paper buy: close={latest.close}, sma={sma}, return_3d={return_3d}"
        if allow_buy
        else f"1d trend blocks paper buy: close={latest.close}, sma={sma}, return_3d={return_3d}"
    )
    return DailyTrendConfirmation(
        allow_buy=allow_buy,
        confidence_boost=Decimal("0.15") if allow_buy else Decimal("0"),
        reason=reason,
        source_ref=f"binance:spot:1d:{latest.closed_at.isoformat()}",
    )


def _snapshot(
    index: int,
    close: Decimal,
    *,
    stale: bool = False,
    exchange_name: str = "sandbox",
    candle: Candle | None = None,
    closed_at: datetime | None = None,
    received_at: datetime | None = None,
    order_book_metrics: OrderBookMetrics | None = None,
) -> PaperMarketSnapshot:
    active_candle = candle or _candle(
        index, close, exchange_name=exchange_name, closed_at=closed_at
    )
    active_received_at = received_at or active_candle.closed_at + timedelta(seconds=1)
    return PaperMarketSnapshot(
        candle=active_candle,
        order_book_metrics=order_book_metrics
        or OrderBookMetrics(
            best_bid=active_candle.close - Decimal("0.01"),
            best_ask=active_candle.close + Decimal("0.01"),
            spread=Decimal("0.02"),
            bid_depth=Decimal("5"),
            ask_depth=Decimal("4"),
            imbalance=Decimal("0.10"),
        ),
        health=StreamHealth(
            is_connected=not stale,
            is_stale=stale,
            is_degraded=stale,
            disconnect_count=1 if stale else 0,
            last_message_at=active_received_at,
            latency_ms=2000 if stale else 10,
            stale_after=timedelta(seconds=30),
        ),
        received_at=active_received_at,
    )


def _candle(
    index: int,
    close: Decimal,
    *,
    exchange_name: str = "sandbox",
    closed_at: datetime | None = None,
) -> Candle:
    active_closed_at = closed_at or DEFAULT_NOW + timedelta(hours=index + 1)
    opened_at = active_closed_at - timedelta(hours=1)
    return Candle(
        exchange=Exchange(exchange_name),
        pair=PAIR,
        interval="1h",
        opened_at=opened_at,
        closed_at=active_closed_at,
        open=close,
        high=close * Decimal("1.005"),
        low=close * Decimal("0.995"),
        close=close,
        volume=Decimal("2"),
    )


def _strategy_state(
    _status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
) -> dict[str, JsonValue]:
    if latest is None:
        return {
            "recommendation": "HOLD",
            "indicator_reasons": ["no paper cycle has run"],
            "ai_confidence": "not_available",
            "risk_decision": "not_evaluated",
            "data_quality": "unavailable",
            "explanation": "Waiting for deterministic paper market data.",
        }
    cycle = latest
    evaluation = cycle.strategy_evaluation
    if cycle.risk_decision_status == "rejected":
        recommendation = "REJECTED"
    elif evaluation is None:
        recommendation = "HOLD"
    else:
        recommendation = evaluation.signal.direction.value.upper()
    reasons = (
        evaluation.reasons if evaluation is not None else (cycle.skipped_reason or "no signal",)
    )
    return {
        "recommendation": recommendation,
        "indicator_reasons": list(reasons),
        "ai_confidence": _str(evaluation.signal.confidence if evaluation else None),
        "risk_decision": cycle.risk_decision_status or "not_evaluated",
        "data_quality": cycle.features.quality.trust_level.value,
        "explanation": "; ".join(reasons),
    }


def _boosted_evaluation(
    evaluation: StrategyEvaluation,
    daily_confirmation: DailyTrendConfirmation,
) -> StrategyEvaluation:
    confidence = min(
        Decimal("1"),
        evaluation.signal.confidence + daily_confirmation.confidence_boost,
    )
    signal = Signal(
        source=evaluation.signal.source,
        pair=evaluation.signal.pair,
        generated_at=evaluation.signal.generated_at,
        direction=evaluation.signal.direction,
        confidence=confidence,
        inputs_ref=evaluation.signal.inputs_ref,
        rationale=f"{evaluation.signal.rationale}; {daily_confirmation.reason}",
        prediction_ref=evaluation.signal.prediction_ref,
    )
    plan = StrategySignalPlan(
        entry_reason=f"{evaluation.plan.entry_reason}; {daily_confirmation.reason}",
        timeframe=evaluation.plan.timeframe,
        feature_snapshot_ref=evaluation.plan.feature_snapshot_ref,
        stop_suggestion=evaluation.plan.stop_suggestion,
        target_suggestion=evaluation.plan.target_suggestion,
        regime_label=evaluation.plan.regime_label,
        prediction_ref=evaluation.plan.prediction_ref,
    )
    return StrategyEvaluation(
        strategy_name=evaluation.strategy_name,
        strategy_version=evaluation.strategy_version,
        enabled=evaluation.enabled,
        signal=signal,
        plan=plan,
        reasons=(*evaluation.reasons, daily_confirmation.reason),
        generated_at=evaluation.generated_at,
        signal_ref=evaluation.signal_ref,
        audit_event_id=evaluation.audit_event_id,
    )


def _daily_blocked_evaluation(
    evaluation: StrategyEvaluation,
    daily_confirmation: DailyTrendConfirmation,
) -> StrategyEvaluation:
    signal = Signal(
        source=evaluation.signal.source,
        pair=evaluation.signal.pair,
        generated_at=evaluation.signal.generated_at,
        direction=SignalDirection.HOLD,
        confidence=Decimal("0"),
        inputs_ref=evaluation.signal.inputs_ref,
        rationale=daily_confirmation.reason,
        prediction_ref=evaluation.signal.prediction_ref,
    )
    plan = StrategySignalPlan(
        entry_reason=daily_confirmation.reason,
        timeframe=evaluation.plan.timeframe,
        feature_snapshot_ref=evaluation.plan.feature_snapshot_ref,
        regime_label=evaluation.plan.regime_label,
        prediction_ref=evaluation.plan.prediction_ref,
    )
    return StrategyEvaluation(
        strategy_name=evaluation.strategy_name,
        strategy_version=evaluation.strategy_version,
        enabled=evaluation.enabled,
        signal=signal,
        plan=plan,
        reasons=(daily_confirmation.reason, *evaluation.reasons),
        generated_at=evaluation.generated_at,
        signal_ref=evaluation.signal_ref,
        audit_event_id=evaluation.audit_event_id,
    )


def _suggested_trade(latest: PaperTradingCycleResult | None) -> dict[str, JsonValue]:
    if latest is None:
        return _empty_trade("waiting for paper strategy evaluation")
    evaluation = latest.strategy_evaluation
    if evaluation is None:
        return _empty_trade("waiting for paper strategy evaluation")
    cycle = latest
    execution = cycle.execution_result
    stop = evaluation.plan.stop_suggestion
    target = evaluation.plan.target_suggestion
    entry = cycle.snapshot.candle.close
    quantity = execution.intent.quantity if execution is not None else Decimal("0")
    risk_amount = _risk_amount(entry=entry, stop=stop, quantity=quantity)
    reward_risk = _reward_risk(entry=entry, stop=stop, target=target)
    return {
        "side": evaluation.signal.direction.value.upper(),
        "simulated_quantity": str(quantity),
        "estimated_entry": str(entry),
        "stop_loss": _str(stop),
        "target": _str(target),
        "risk_amount": str(risk_amount),
        "reward_to_risk": _str(reward_risk),
        "status": "risk_approved_simulated_fill" if cycle.executed else "not_executable",
    }


def _empty_trade(reason: str) -> dict[str, JsonValue]:
    return {
        "side": "HOLD",
        "simulated_quantity": "0",
        "estimated_entry": "not_available",
        "stop_loss": "not_available",
        "target": "not_available",
        "risk_amount": "0",
        "reward_to_risk": "not_available",
        "status": reason,
    }


def _transaction_state(trades: tuple[PaperTrade, ...]) -> list[JsonValue]:
    return [
        {
            "time": trade.occurred_at.isoformat(),
            "side": trade.side.value.upper(),
            "quantity": str(trade.quantity),
            "price": str(trade.price),
            "fee": str(trade.fee_paid),
            "notional": str(trade.notional),
        }
        for trade in reversed(trades)
    ]


def _adaptive_view_sections(
    *,
    payload: Mapping[str, JsonValue],
    status: PaperStatusResponse,
    cycles: tuple[PaperTradingCycleResult, ...],
    latest: PaperTradingCycleResult | None,
    can_approve: bool,
    strategy_lab_selection: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    strategy = _as_mapping(payload["strategy"])
    portfolio = _as_mapping(payload["portfolio"])
    controls = _as_mapping(payload["controls"])
    market = _as_mapping(payload["market"])
    trade = _as_mapping(payload["suggested_paper_trade"])
    transactions = _as_list(payload["transactions"])
    logs = _as_list(payload["logs"])
    reasons = _as_text_list(strategy.get("indicator_reasons", []))
    actionable = can_approve and str(trade.get("status", "")) == "risk_approved_simulated_fill"
    recommendation = str(strategy.get("recommendation", "HOLD"))
    evidence_status = "available" if latest is not None else "missing"
    market_payload = dict(market)
    strategy_payload = dict(strategy)
    trade_payload = dict(trade)
    portfolio_payload = dict(portfolio)
    controls_payload = dict(controls)
    return {
        DashboardUIMode.BEGINNER.value: {
            "enabled_modules": [
                "paper_dashboard_controller",
                "paper_trading_engine",
                "risk_engine",
                "market_data_adapter_read_only",
                "paper_account_persistence",
                "basic_strategy_explanation",
            ],
            "status_banner": {
                "paper_mode": True,
                "safe_mode": True,
                "live_trading_enabled": False,
            },
            "command": _beginner_command(
                recommendation=recommendation,
                actionable=actionable,
                trade=trade,
                controls=controls,
            ),
            "reasons": _beginner_reasons(reasons, recommendation=recommendation),
            "portfolio_summary": _beginner_portfolio_summary(portfolio),
            "transactions": _beginner_transactions(transactions),
            "glossary": _beginner_glossary(),
        },
        DashboardUIMode.ADVANCED_TRADER.value: {
            "enabled_modules": [
                "paper_trading_engine",
                "risk_engine",
                "portfolio_manager",
                "market_data_adapter_read_only",
                "indicators_feature_pipeline",
                "backtest_summary",
                "performance_analytics",
                "position_exit_review",
                "paper_ledger",
                "audit_evidence",
            ],
            "market": market_payload,
            "strategy": strategy_payload,
            "suggested_paper_trade": trade_payload,
            "portfolio": portfolio_payload,
            "controls": controls_payload,
            "transactions": transactions,
            "logs": logs,
            "chart": _advanced_chart_payload(cycles),
            "backtest_summary": _advanced_backtest_summary(status=status, latest=latest),
            "performance": _advanced_performance_summary(status=status),
            "exit_review": _advanced_exit_review(
                status=status,
                latest=latest,
                trade=trade,
            ),
            "exports": {
                "transactions_csv": "/paper-transactions.csv",
                "paper_report": "/paper-report",
            },
        },
        DashboardUIMode.STRATEGY_LAB.value: _strategy_lab_view(
            selection=strategy_lab_selection,
            default_symbol=str(market.get("symbol", "BTC/USDT")),
            strategy=strategy_payload,
            actionable=actionable,
            evidence_status=evidence_status,
        ),
    }


def _strategy_lab_view(
    *,
    selection: Mapping[str, JsonValue],
    default_symbol: str,
    strategy: Mapping[str, JsonValue],
    actionable: bool,
    evidence_status: str,
) -> dict[str, JsonValue]:
    selected_key = str(selection.get("strategy", "min_risk_spot_v1"))
    profile = _strategy_profile(selected_key)
    symbol = str(selection.get("symbol", default_symbol))
    timeframe = str(selection.get("timeframe", profile["default_timeframe"]))
    run_mode = str(selection.get("run_mode", StrategyLabRunMode.PAPER.value))
    parameter_profile = str(selection.get("parameter_profile", "default"))
    missing_evidence = _strategy_lab_missing_evidence(profile, strategy)
    is_selected_supported = (
        symbol in _as_text_tuple(profile["symbols"])
        and timeframe in _as_text_tuple(profile["timeframes"])
        and parameter_profile in _as_text_tuple(profile["parameter_profiles"])
    )
    recommendation_actionable = (
        actionable
        and evidence_status == "available"
        and not missing_evidence
        and profile["paper_approval_allowed"] is True
        and run_mode == StrategyLabRunMode.PAPER.value
        and is_selected_supported
    )
    return {
        "enabled_modules": list(_as_text_tuple(profile["enabled_modules"])),
        "selected_strategy": profile["label"],
        "selection": {
            "strategy": profile["key"],
            "symbol": symbol,
            "timeframe": timeframe,
            "run_mode": run_mode,
            "parameter_profile": parameter_profile,
        },
        "selectors": {
            "strategies": _strategy_selector_options(),
            "symbols": list(_as_text_tuple(profile["symbols"])),
            "timeframes": list(_as_text_tuple(profile["timeframes"])),
            "run_modes": [item.value for item in StrategyLabRunMode],
            "parameter_profiles": list(_as_text_tuple(profile["parameter_profiles"])),
        },
        "paper_approval_allowed": profile["paper_approval_allowed"],
        "evidence_status": "missing" if missing_evidence else evidence_status,
        "recommendation_actionable": recommendation_actionable,
        "required_evidence": list(_as_text_tuple(profile["required_evidence"])),
        "missing_evidence": missing_evidence,
        "required_market_data": list(_as_text_tuple(profile["required_market_data"])),
        "required_indicators": list(_as_text_tuple(profile["required_indicators"])),
        "required_risk_checks": list(_as_text_tuple(profile["required_risk_checks"])),
        "required_explanation_fields": list(_as_text_tuple(profile["required_explanation_fields"])),
        "chart_overlays": list(_as_text_tuple(profile["chart_overlays"])),
        "backtest_metrics": list(_as_text_tuple(profile["backtest_metrics"])),
        "strategy_state": dict(strategy),
        "compare_runs": _strategy_lab_compare_runs(profile),
        "limitations": _strategy_lab_limitations(run_mode, recommendation_actionable),
    }


def _strategy_profile(key: str) -> dict[str, JsonValue]:
    profiles = _strategy_profiles()
    if key not in profiles:
        allowed = ", ".join(sorted(profiles))
        raise PaperDashboardActionError(f"unknown strategy profile: {key}; expected {allowed}")
    return profiles[key]


def _strategy_profiles() -> dict[str, dict[str, JsonValue]]:
    return {
        "min_risk_spot_v1": {
            "key": "min_risk_spot_v1",
            "label": "MinRiskSpotStrategyV1",
            "family": "defensive_spot",
            "status": "paper_active",
            "description": (
                "Conservative long-only BTC spot strategy focused on capital protection."
            ),
            "symbols": ["BTC/USDT"],
            "timeframes": ["15m", "1h", "4h", "1d"],
            "default_timeframe": "1h",
            "parameter_profiles": ["default", "defensive"],
            "paper_approval_allowed": True,
            "enabled_modules": [
                "strategy_profile_registry",
                "paper_trading_engine",
                "risk_engine",
                "market_data_adapter_read_only",
                "indicators_feature_pipeline",
                "strategy_explanation",
                "paper_evaluation_gate",
            ],
            "required_evidence": [
                "market_data",
                "indicator_features",
                "risk_decision",
                "explanation_fields",
                "paper_account_state",
            ],
            "required_market_data": ["BTC/USDT candles", "order book spread", "stream health"],
            "required_indicators": ["return_3", "RSI", "ATR percent", "volume ratio", "spread bps"],
            "required_risk_checks": [
                "stop loss required",
                "max spread",
                "max slippage",
                "drawdown halt",
                "cash reserve",
            ],
            "required_explanation_fields": [
                "recommendation",
                "ai_confidence",
                "risk_decision",
                "data_quality",
                "indicator_reasons",
            ],
            "chart_overlays": ["SMA 3", "signal markers", "stop loss", "target"],
            "backtest_metrics": [
                "win_rate",
                "expectancy",
                "drawdown",
                "sharpe",
                "sortino",
                "profit_factor",
                "fees",
                "slippage",
                "sample_size",
            ],
        }
    }


def _strategy_selector_options() -> list[JsonValue]:
    return [
        {
            "value": profile["key"],
            "label": profile["label"],
            "status": profile["status"],
        }
        for profile in _strategy_profiles().values()
    ]


def _strategy_lab_missing_evidence(
    profile: Mapping[str, JsonValue],
    strategy: Mapping[str, JsonValue],
) -> list[JsonValue]:
    missing: list[JsonValue] = []
    required_fields = _as_text_tuple(profile["required_explanation_fields"])
    for field_name in required_fields:
        value = strategy.get(field_name)
        if value in (None, "", "not_available"):
            missing.append(field_name)
    return missing


def _strategy_lab_compare_runs(profile: Mapping[str, JsonValue]) -> list[JsonValue]:
    return [
        {
            "run_id": "current_paper",
            "strategy": profile["label"],
            "parameter_profile": "default",
            "mode": "paper",
            "status": "current dashboard run",
        },
        {
            "run_id": "defensive_profile",
            "strategy": profile["label"],
            "parameter_profile": "defensive",
            "mode": "backtest",
            "status": "ready for Stage D comparison inputs",
        },
    ]


def _strategy_lab_limitations(
    run_mode: str,
    recommendation_actionable: bool,
) -> list[JsonValue]:
    limitations: list[JsonValue] = [
        "Strategy Lab remains paper-only and cannot enable live orders."
    ]
    if run_mode == StrategyLabRunMode.BACKTEST.value:
        limitations.append("Backtest mode is research-only; paper approval is disabled.")
    if not recommendation_actionable:
        limitations.append(
            "Recommendation is not actionable until all required evidence is present."
        )
    return limitations


def _strategy_lab_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if symbol != "BTC/USDT":
        raise PaperDashboardActionError("Stage D Strategy Lab supports BTC/USDT only")
    return symbol


def _strategy_lab_timeframe(value: str, strategy_key: str) -> str:
    timeframe = value.strip()
    profile = _strategy_profile(strategy_key)
    if timeframe not in _as_text_tuple(profile["timeframes"]):
        raise PaperDashboardActionError(f"unsupported timeframe for {strategy_key}: {timeframe}")
    return timeframe


def _strategy_lab_run_mode(value: str) -> StrategyLabRunMode:
    try:
        return StrategyLabRunMode(value.strip())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in StrategyLabRunMode)
        message = f"unsupported Strategy Lab mode: {value}; expected {allowed}"
        raise PaperDashboardActionError(message) from exc


def _strategy_lab_parameter_profile(value: str, strategy_key: str) -> str:
    parameter_profile = value.strip()
    profile = _strategy_profile(strategy_key)
    if parameter_profile not in _as_text_tuple(profile["parameter_profiles"]):
        raise PaperDashboardActionError(
            f"unsupported parameter profile for {strategy_key}: {parameter_profile}"
        )
    return parameter_profile


def _as_text_tuple(value: JsonValue) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _advanced_chart_payload(cycles: tuple[PaperTradingCycleResult, ...]) -> dict[str, JsonValue]:
    candles: list[JsonValue] = []
    indicators: list[JsonValue] = []
    markers: list[JsonValue] = []
    closes: list[Decimal] = []
    for cycle in cycles:
        candle = cycle.snapshot.candle
        closes.append(candle.close)
        candles.append(
            {
                "time": candle.closed_at.isoformat(),
                "open": str(candle.open),
                "high": str(candle.high),
                "low": str(candle.low),
                "close": str(candle.close),
                "volume": str(candle.volume),
            }
        )
        sma_window = closes[-3:]
        sma = sum(sma_window, DECIMAL_ZERO) / Decimal(len(sma_window))
        indicators.append(
            {
                "time": candle.closed_at.isoformat(),
                "sma_3": str(sma),
            }
        )
        if cycle.strategy_evaluation is not None:
            markers.append(
                {
                    "time": candle.closed_at.isoformat(),
                    "price": str(candle.close),
                    "signal": cycle.strategy_evaluation.signal.direction.value.upper(),
                    "risk_decision": cycle.risk_decision_status or "not_evaluated",
                    "audit_ref": str(cycle.strategy_evaluation.audit_event_id or ""),
                }
            )
    latest = cycles[-1] if cycles else None
    evaluation = latest.strategy_evaluation if latest is not None else None
    return {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "candles": candles,
        "indicators": indicators,
        "markers": markers,
        "risk_lines": {
            "entry": _str(latest.snapshot.candle.close if latest is not None else None),
            "stop_loss": _str(evaluation.plan.stop_suggestion if evaluation else None),
            "target": _str(evaluation.plan.target_suggestion if evaluation else None),
        },
    }


def _advanced_backtest_summary(
    *,
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
) -> dict[str, JsonValue]:
    sample_size = status.cycles_count
    return {
        "status": "paper_sample_only",
        "sample_size": str(sample_size),
        "win_rate": "not_available",
        "expectancy": "not_available",
        "max_drawdown": str(status.portfolio.drawdown_pct),
        "sharpe": "not_available",
        "sortino": "not_available",
        "profit_factor": "not_available",
        "fees": str(status.portfolio.fees_paid),
        "slippage": "paper_fill_model",
        "latest_signal_ref": _latest_signal_ref(latest),
        "sample_size_warning": _sample_size_warning(sample_size),
    }


def _advanced_performance_summary(status: PaperStatusResponse) -> dict[str, JsonValue]:
    current_equity = status.portfolio.equity
    total_return = (
        current_equity / Decimal("10000") - Decimal("1") if current_equity else DECIMAL_ZERO
    )
    return {
        "daily": _pct(total_return),
        "weekly": _pct(total_return),
        "monthly": _pct(total_return),
        "long_term": _pct(total_return),
        "current_equity": str(current_equity),
        "cash": str(status.portfolio.cash),
        "open_btc": str(status.portfolio.base_quantity),
        "realized_pnl": str(status.portfolio.realized_pnl),
        "unrealized_pnl": _unrealized_pnl(status),
        "drawdown": str(status.portfolio.drawdown_pct),
        "fees_paid": str(status.portfolio.fees_paid),
        "trades": str(status.trades_count),
    }


def _advanced_exit_review(
    *,
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
    trade: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    if status.portfolio.base_quantity <= DECIMAL_ZERO:
        return {
            "recommendation": "no_open_position",
            "reason": "No open paper BTC position to review.",
            "stop_loss": str(trade.get("stop_loss", "not_available")),
            "target": str(trade.get("target", "not_available")),
            "risk_decision": latest.risk_decision_status if latest else "not_evaluated",
        }
    latest_signal = (
        latest.strategy_evaluation.signal.direction.value.upper()
        if latest is not None and latest.strategy_evaluation is not None
        else "HOLD"
    )
    recommendation = "hold"
    if latest_signal == "SELL":
        recommendation = "exit_review"
    elif latest_signal == "BUY":
        recommendation = "hold_existing_or_add_only_after_approval"
    return {
        "recommendation": recommendation,
        "reason": "Paper position review uses current signal, risk lines, and account exposure.",
        "open_btc": str(status.portfolio.base_quantity),
        "average_entry": str(status.portfolio.average_entry_price),
        "current_price": _str(status.current_btc_price),
        "stop_loss": str(trade.get("stop_loss", "not_available")),
        "target": str(trade.get("target", "not_available")),
        "risk_decision": latest.risk_decision_status if latest else "not_evaluated",
    }


def _latest_signal_ref(latest: PaperTradingCycleResult | None) -> str:
    if latest is None or latest.strategy_evaluation is None:
        return "not_available"
    return str(latest.strategy_evaluation.signal_ref)


def _sample_size_warning(sample_size: int) -> str:
    if sample_size < 30:
        return "Very small sample; do not treat this as proven strategy performance."
    return "Sample size is still paper-only and must be reviewed before live use."


def _pct(value: Decimal) -> str:
    return str(value * Decimal("100"))


def _beginner_command(
    *,
    recommendation: str,
    actionable: bool,
    trade: Mapping[str, JsonValue],
    controls: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    normalized = recommendation.upper()
    if not actionable or normalized in {"HOLD", "REJECTED", "WAIT"}:
        return {
            "label": "Do nothing now",
            "action": "do_nothing",
            "actionable": False,
            "approval_enabled": False,
            "plain_status": _beginner_block_status(normalized, controls),
            "next_step": "Keep watching paper mode. No approval is needed.",
        }
    if normalized == "SELL":
        label = "SELL REVIEW"
        next_step = "Review the paper sell before approving it."
    else:
        label = "BUY"
        next_step = "Approve only if you want to apply this simulated paper trade."
    return {
        "label": label,
        "action": normalized.lower(),
        "actionable": True,
        "approval_enabled": True,
        "plain_status": (
            "The bot found a risk-approved paper trade. This still cannot place a real order."
        ),
        "next_step": next_step,
        "paper_quantity": str(trade.get("simulated_quantity", "0")),
        "estimated_price": str(trade.get("estimated_entry", "not_available")),
    }


def _beginner_block_status(
    recommendation: str,
    controls: Mapping[str, JsonValue],
) -> str:
    if recommendation == "HOLD":
        return "The bot is choosing to wait."
    if recommendation == "REJECTED":
        return "The risk checks blocked the paper trade."
    reason = str(controls.get("approval_block_reason", "latest recommendation is not executable"))
    return f"Approval is off because {reason}."


def _beginner_reasons(
    reasons: list[JsonValue],
    *,
    recommendation: str,
) -> list[JsonValue]:
    plain_reasons: list[JsonValue] = [str(reason) for reason in reasons[:5]]
    if recommendation.upper() == "HOLD":
        return ["The safest action is to wait right now.", *plain_reasons]
    return plain_reasons or ["No beginner explanation is available yet."]


def _beginner_portfolio_summary(portfolio: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        "paper_cash": str(portfolio.get("cash", "not_available")),
        "paper_account_value": str(portfolio.get("current_equity", "not_available")),
        "open_btc": str(portfolio.get("open_btc", "not_available")),
        "paper_profit_loss": str(portfolio.get("realized_pnl", "not_available")),
        "unrealized_profit_loss": str(portfolio.get("unrealized_pnl", "not_available")),
        "safety_status": _beginner_safety_status(portfolio),
    }


def _beginner_safety_status(portfolio: Mapping[str, JsonValue]) -> str:
    risk_halts = portfolio.get("risk_halts", [])
    if isinstance(risk_halts, list) and risk_halts and str(risk_halts[0]) != "none":
        return f"Paused by safety check: {risk_halts[0]}"
    return "No paper safety halt is active."


def _beginner_transactions(transactions: list[JsonValue]) -> list[JsonValue]:
    beginner_rows: list[JsonValue] = []
    for item in transactions[:10]:
        if not isinstance(item, Mapping):
            continue
        beginner_rows.append(
            {
                "time": str(item.get("time", "not_available")),
                "paper_action": str(item.get("side", "not_available")),
                "btc_amount": str(item.get("quantity", "not_available")),
                "paper_price": str(item.get("price", "not_available")),
                "paper_value": str(item.get("notional", "not_available")),
            }
        )
    return beginner_rows


def _beginner_glossary() -> list[JsonValue]:
    return [
        {
            "term": "Paper mode",
            "meaning": "Practice trading with simulated money. No real exchange order is placed.",
        },
        {
            "term": "Safe mode",
            "meaning": "Risk checks can block or pause paper trades before approval.",
        },
        {
            "term": "BUY",
            "meaning": (
                "The bot found a risk-approved simulated buy you can approve for paper mode."
            ),
        },
        {
            "term": "HOLD",
            "meaning": "The bot is waiting. In beginner view this means do nothing now.",
        },
        {
            "term": "P/L",
            "meaning": "Profit or loss in the paper account.",
        },
    ]


def _dashboard_readiness_gate(
    *,
    payload: Mapping[str, JsonValue],
    cycles: tuple[PaperTradingCycleResult, ...],
    events: list[PaperDashboardEvent],
    db_path: str | None,
    state_path: str | None,
) -> dict[str, JsonValue]:
    views = _as_mapping(payload["views"])
    beginner = _as_mapping(views.get(DashboardUIMode.BEGINNER.value, {}))
    advanced = _as_mapping(views.get(DashboardUIMode.ADVANCED_TRADER.value, {}))
    strategy_lab = _as_mapping(views.get(DashboardUIMode.STRATEGY_LAB.value, {}))
    controls = _as_mapping(payload["controls"])
    unsupported_markets = _as_mapping(payload["unsupported_markets"])
    transactions = _as_list(payload["transactions"])
    route_checks = _paper_safe_route_checks()
    reconstructability = _paper_trade_reconstructability(
        cycles=cycles,
        transactions=transactions,
        events=events,
    )
    checklist: list[JsonValue] = [
        _readiness_item(
            "beginner_view_tested",
            "Beginner view has tested safe controls",
            _has_keys(beginner, ("command", "portfolio_summary", "transactions", "glossary")),
            "Beginner state includes command, portfolio, transaction, and glossary sections.",
        ),
        _readiness_item(
            "advanced_view_tested",
            "Advanced Trader view has tested audit evidence",
            _has_keys(
                advanced,
                (
                    "chart",
                    "backtest_summary",
                    "performance",
                    "exit_review",
                    "exports",
                ),
            ),
            "Advanced state includes chart, metrics, exit review, and export sections.",
        ),
        _readiness_item(
            "strategy_lab_view_tested",
            "Strategy Lab view has tested module routing",
            _has_keys(
                strategy_lab,
                ("selectors", "required_evidence", "compare_runs", "limitations"),
            ),
            "Strategy Lab state includes selectors, evidence requirements, and comparisons.",
        ),
        _readiness_item(
            "paper_only_permissions",
            "UI and controls are paper-only",
            payload.get("live_trading_enabled") is False
            and payload.get("safe_mode") is True
            and controls.get("can_enable_live_trading") is None,
            "Dashboard state keeps live trading disabled and exposes no live-enable control.",
        ),
        _readiness_item(
            "unsupported_markets_disabled",
            "Unsupported market routes are disabled",
            all(value is False for value in unsupported_markets.values()),
            "Leverage, margin, futures, options, withdrawals, and transfers remain unavailable.",
        ),
        _readiness_item(
            "backend_routes_paper_safe",
            "Backend routes are paper-safe",
            all(_as_mapping(item).get("paper_safe") is True for item in route_checks),
            "All dashboard routes are read-only, preference-only, or paper-control only.",
        ),
        _readiness_item(
            "paper_trade_reconstructability",
            "Paper trades are reconstructable",
            reconstructability["reconstructable"] is True,
            str(reconstructability["detail"]),
        ),
        _readiness_item(
            "persistence_configured",
            "Paper ledger persistence is configured",
            db_path is not None or state_path is not None,
            "SQLite is configured." if db_path is not None else "JSON fallback is configured.",
        ),
        _readiness_item(
            "sqlite_ledger_enabled",
            "SQLite paper ledger is enabled",
            db_path is not None,
            "SQLite repository is the main ledger when ABTP_PAPER_DB_PATH is configured.",
            blocking=False,
        ),
    ]
    ready = all(
        _as_mapping(item).get("passed") is True
        for item in checklist
        if _as_mapping(item).get("blocking") is True
    )
    return {
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "summary": (
            "Trader readiness gate passed." if ready else "Trader readiness gate has blockers."
        ),
        "live_trading_enabled": False,
        "paper_safe": all(_as_mapping(item).get("paper_safe") is True for item in route_checks),
        "views_checked": [
            DashboardUIMode.BEGINNER.value,
            DashboardUIMode.ADVANCED_TRADER.value,
            DashboardUIMode.STRATEGY_LAB.value,
        ],
        "routes": route_checks,
        "trade_reconstructability": reconstructability,
        "checklist": checklist,
    }


def _readiness_item(
    item_id: str,
    label: str,
    passed: bool,
    detail: str,
    *,
    blocking: bool = True,
) -> dict[str, JsonValue]:
    return {
        "id": item_id,
        "label": label,
        "status": "pass" if passed else "blocker",
        "passed": passed,
        "blocking": blocking,
        "detail": detail,
    }


def _has_keys(payload: Mapping[str, JsonValue], keys: tuple[str, ...]) -> bool:
    return all(key in payload for key in keys)


def _paper_safe_route_checks() -> list[JsonValue]:
    routes = (
        ("GET /", "Dashboard shell only"),
        ("GET /api/status", "Read-only paper dashboard status"),
        ("GET /api/readiness", "Read-only readiness checklist"),
        ("GET /paper-report", "Read-only paper report export"),
        ("GET /paper-transactions.csv", "Read-only paper transaction export"),
        ("POST /api/ui-mode", "UI preference only"),
        ("POST /api/strategy-lab-selection", "Strategy Lab preference only"),
        ("POST /api/approve-paper-trade", "Applies simulated paper fill only"),
        ("POST /api/reject-recommendation", "Records paper operator rejection"),
        ("POST /api/pause-paper-bot", "Pauses paper bot only"),
        ("POST /api/resume-paper-bot", "Resumes paper bot only"),
        ("POST /api/emergency-stop", "Activates paper dashboard kill switch"),
        ("POST /api/reset-emergency-stop", "Resets paper dashboard kill switch"),
    )
    return [
        {
            "route": route,
            "purpose": purpose,
            "paper_safe": True,
            "live_order_capability": False,
        }
        for route, purpose in routes
    ]


def _paper_trade_reconstructability(
    *,
    cycles: tuple[PaperTradingCycleResult, ...],
    transactions: list[JsonValue],
    events: list[PaperDashboardEvent],
) -> dict[str, JsonValue]:
    latest_executed = next((cycle for cycle in reversed(cycles) if cycle.executed), None)
    if latest_executed is None:
        return {
            "reconstructable": not transactions,
            "status": "no_paper_trade_yet",
            "detail": "No simulated paper trade has been accepted yet.",
            "checks": [],
        }
    execution = latest_executed.execution_result
    route_result = execution.route_result if execution is not None else None
    fills = route_result.fills if route_result is not None else ()
    checks: list[JsonValue] = [
        _readiness_item(
            "market_data",
            "Market data snapshot",
            latest_executed.snapshot.candle.close > DECIMAL_ZERO,
            "Candle, order-book metrics, stream health, and timestamp are present.",
        ),
        _readiness_item(
            "features",
            "Feature snapshot",
            bool(latest_executed.features.source_refs),
            "Feature source references are present.",
        ),
        _readiness_item(
            "strategy_signal",
            "Strategy signal",
            latest_executed.strategy_evaluation is not None,
            "Strategy evaluation, signal direction, confidence, and reasons are present.",
        ),
        _readiness_item(
            "risk_decision",
            "Risk decision",
            latest_executed.risk_decision_status is not None,
            "Risk Management Engine decision status is present.",
        ),
        _readiness_item(
            "simulated_fill",
            "Simulated fill",
            execution is not None and route_result is not None and bool(fills),
            "Paper-safe execution fill, idempotency key, fee, and route result are present.",
        ),
        _readiness_item(
            "account_update",
            "Paper account update",
            bool(transactions),
            "Paper account transaction row is visible in the dashboard ledger.",
        ),
        _readiness_item(
            "operator_or_audit_action",
            "Operator or audit action",
            any(
                event.event_type
                in {
                    DashboardAction.APPROVE_PAPER_TRADE.value,
                    DashboardAction.REJECT_RECOMMENDATION.value,
                    "paper_fill",
                }
                for event in events
            ),
            "A paper-fill audit event or operator decision event is present.",
        ),
    ]
    reconstructable = all(_as_mapping(item).get("passed") is True for item in checks)
    return {
        "reconstructable": reconstructable,
        "status": "reconstructable" if reconstructable else "missing_evidence",
        "detail": (
            "Latest simulated paper trade has market data, features, signal, risk, fill, "
            "account, and operator/audit evidence."
            if reconstructable
            else "Latest simulated paper trade is missing required audit evidence."
        ),
        "checks": checks,
    }


def _ui_mode(value: DashboardUIMode | str) -> DashboardUIMode:
    try:
        return value if isinstance(value, DashboardUIMode) else DashboardUIMode(str(value))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in DashboardUIMode)
        message = f"unsupported dashboard UI mode: {value}; expected {allowed}"
        raise PaperDashboardActionError(message) from exc


def _save_dashboard_preferences(controller: PaperDashboardController) -> None:
    _save_paper_account_state(controller)


def _save_paper_account_state(controller: PaperDashboardController) -> None:
    if controller.state_path is None and controller.db_path is None:
        return
    payload = _paper_dashboard_state_payload(controller)
    if controller.db_path is not None:
        try:
            with _paper_dashboard_repository(controller.db_path) as repository:
                repository.save_state_payload(
                    payload,
                    strategy_evaluations=_paper_strategy_evaluation_payloads(controller),
                    risk_decisions=_paper_risk_decision_payloads(controller),
                    simulated_fills=_paper_simulated_fill_payloads(controller),
                    operator_actions=[event.as_dict() for event in controller.events],
                )
        except (OSError, ValueError) as exc:
            controller.events.insert(
                0,
                PaperDashboardEvent(
                    event_type="paper_sqlite_save_failed",
                    message="SQLite paper state save failed; JSON export remains available.",
                    reason=str(exc),
                    occurred_at=_latest_time(controller.engine),
                ),
            )
    if controller.state_path is not None:
        path = Path(controller.state_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _restore_paper_account_state(controller: PaperDashboardController) -> None:
    if controller.db_path is not None:
        try:
            with _paper_dashboard_repository(controller.db_path) as repository:
                payload = repository.load_latest_state_payload()
            if payload is not None:
                _restore_paper_payload(controller, payload, source_ref=controller.db_path)
                return
        except (OSError, ValueError, TypeError) as exc:
            controller.events.insert(
                0,
                PaperDashboardEvent(
                    event_type="paper_sqlite_restore_failed",
                    message="SQLite paper wallet could not be restored; checking JSON fallback.",
                    reason=str(exc),
                    occurred_at=_latest_time(controller.engine),
                ),
            )
    if controller.state_path is None:
        return
    path = Path(controller.state_path)
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("paper state file must contain a JSON object")
        _restore_paper_payload(controller, payload, source_ref=str(path))
    except (OSError, ValueError, TypeError) as exc:
        controller.events.insert(
            0,
            PaperDashboardEvent(
                event_type="paper_state_restore_failed",
                message="Saved paper wallet could not be restored; fresh paper wallet loaded.",
                reason=str(exc),
                occurred_at=_latest_time(controller.engine),
            ),
        )


def _paper_dashboard_state_payload(controller: PaperDashboardController) -> dict[str, JsonValue]:
    state = controller.engine.account.state
    return {
        "version": 2,
        "updated_at": _latest_time(controller.engine).isoformat(),
        "market_data_source": controller.market_data_source,
        "ui_preferences": {
            "mode": controller.ui_mode.value,
            "strategy_lab": {
                "strategy": controller.strategy_lab_strategy,
                "symbol": controller.strategy_lab_symbol,
                "timeframe": controller.strategy_lab_timeframe,
                "run_mode": controller.strategy_lab_run_mode.value,
                "parameter_profile": controller.strategy_lab_parameter_profile,
            },
        },
        "account": {
            "cash": str(state.cash),
            "base_quantity": str(state.base_quantity),
            "average_entry_price": str(state.average_entry_price),
            "realized_pnl": str(state.realized_pnl),
            "fees_paid": str(state.fees_paid),
            "equity_history": [str(value) for value in state.equity_history],
        },
        "trades": [_paper_trade_as_dict(trade) for trade in controller.engine.account.trades],
    }


def _restore_paper_payload(
    controller: PaperDashboardController,
    payload: Mapping[str, JsonValue],
    *,
    source_ref: str,
) -> None:
    preferences = payload.get("ui_preferences", {})
    if isinstance(preferences, Mapping):
        controller.ui_mode = _ui_mode(str(preferences.get("mode", controller.ui_mode.value)))
        strategy_lab = preferences.get("strategy_lab", {})
        if isinstance(strategy_lab, Mapping):
            restored_strategy = _strategy_profile(
                str(strategy_lab.get("strategy", controller.strategy_lab_strategy))
            )["key"]
            controller.strategy_lab_strategy = str(restored_strategy)
            controller.strategy_lab_symbol = _strategy_lab_symbol(
                str(strategy_lab.get("symbol", controller.strategy_lab_symbol))
            )
            controller.strategy_lab_timeframe = _strategy_lab_timeframe(
                str(strategy_lab.get("timeframe", controller.strategy_lab_timeframe)),
                controller.strategy_lab_strategy,
            )
            controller.strategy_lab_run_mode = _strategy_lab_run_mode(
                str(strategy_lab.get("run_mode", controller.strategy_lab_run_mode.value))
            )
            controller.strategy_lab_parameter_profile = _strategy_lab_parameter_profile(
                str(
                    strategy_lab.get(
                        "parameter_profile",
                        controller.strategy_lab_parameter_profile,
                    )
                ),
                controller.strategy_lab_strategy,
            )
    account_payload = payload.get("account")
    if not isinstance(account_payload, Mapping):
        raise ValueError("paper state payload is missing account balances")
    trades_payload = payload.get("trades", [])
    if not isinstance(trades_payload, list):
        raise ValueError("paper state trades must be a list")
    account_state = _paper_account_state_from_mapping(account_payload)
    trades = tuple(
        _paper_trade_from_mapping(item) for item in trades_payload if isinstance(item, Mapping)
    )
    controller.engine.account.restore_state(account_state, trades)
    controller.events.insert(
        0,
        PaperDashboardEvent(
            event_type="paper_state_restored",
            message="Saved paper wallet restored for this local dashboard.",
            reason=source_ref,
            occurred_at=_latest_time(controller.engine),
        ),
    )


def _paper_strategy_evaluation_payloads(
    controller: PaperDashboardController,
) -> tuple[Mapping[str, JsonValue], ...]:
    payloads: list[Mapping[str, JsonValue]] = []
    for cycle in controller.engine.cycles:
        evaluation = cycle.strategy_evaluation
        if evaluation is None:
            continue
        payloads.append(
            {
                "strategy_name": evaluation.strategy_name,
                "strategy_version": evaluation.strategy_version,
                "signal_direction": evaluation.signal.direction.value,
                "generated_at": evaluation.generated_at.isoformat(),
                "signal_ref": evaluation.signal_ref,
                "audit_event_id": str(evaluation.audit_event_id or ""),
                "reasons": list(evaluation.reasons),
                "feature_snapshot_ref": evaluation.plan.feature_snapshot_ref,
                "risk_decision_status": cycle.risk_decision_status or "not_evaluated",
                "data_quality": cycle.features.quality.trust_level.value,
            }
        )
    return tuple(payloads)


def _paper_risk_decision_payloads(
    controller: PaperDashboardController,
) -> tuple[Mapping[str, JsonValue], ...]:
    payloads: list[Mapping[str, JsonValue]] = []
    for cycle in controller.engine.cycles:
        if cycle.risk_decision_status is None:
            continue
        execution = cycle.execution_result
        payloads.append(
            {
                "order_intent_id": str(execution.intent.id) if execution is not None else None,
                "status": cycle.risk_decision_status,
                "evaluated_at": cycle.snapshot.received_at.isoformat(),
                "accepted": execution.accepted if execution is not None else False,
                "reason": execution.reason or "" if execution is not None else "",
            }
        )
    return tuple(payloads)


def _paper_simulated_fill_payloads(
    controller: PaperDashboardController,
) -> tuple[Mapping[str, JsonValue], ...]:
    payloads: list[Mapping[str, JsonValue]] = []
    for cycle in controller.engine.cycles:
        execution = cycle.execution_result
        if execution is None or execution.route_result is None:
            continue
        for fill in execution.route_result.fills:
            payloads.append(
                {
                    "order_intent_id": str(fill.order_intent_id),
                    "side": execution.intent.side.value,
                    "quantity": str(fill.filled_quantity),
                    "price": str(fill.average_fill_price),
                    "fee_paid": str(fill.fee_paid),
                    "occurred_at": fill.occurred_at.isoformat(),
                    "exchange_order_id": fill.exchange_order_id,
                    "liquidity": fill.liquidity,
                    "idempotency_key": execution.idempotency_key,
                }
            )
    return tuple(payloads)


class _PaperDashboardRepositoryContext:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._connection: Connection | None = None

    def __enter__(self) -> PaperDashboardRepository:
        path = Path(self._db_path)
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = connect_database(self._db_path)
        apply_migrations(self._connection)
        return PaperDashboardRepository(self._connection)

    def __exit__(self, *_exc: object) -> None:
        if self._connection is not None:
            self._connection.close()


def _paper_dashboard_repository(db_path: str) -> _PaperDashboardRepositoryContext:
    return _PaperDashboardRepositoryContext(db_path)


def _paper_account_state_from_mapping(payload: Mapping[str, JsonValue]) -> PaperAccountState:
    equity_history_payload = payload.get("equity_history", ())
    if not isinstance(equity_history_payload, list):
        equity_history_payload = []
    equity_history = tuple(_decimal(value) for value in equity_history_payload)
    cash = _decimal(payload.get("cash", "10000"))
    return PaperAccountState(
        cash=cash,
        base_quantity=_decimal(payload.get("base_quantity", "0")),
        average_entry_price=_decimal(payload.get("average_entry_price", "0")),
        realized_pnl=_decimal(payload.get("realized_pnl", "0")),
        fees_paid=_decimal(payload.get("fees_paid", "0")),
        equity_history=equity_history or (cash,),
    )


def _paper_trade_as_dict(trade: PaperTrade) -> dict[str, JsonValue]:
    return {
        "order_intent_id": str(trade.order_intent_id),
        "side": trade.side.value,
        "quantity": str(trade.quantity),
        "price": str(trade.price),
        "fee_paid": str(trade.fee_paid),
        "occurred_at": trade.occurred_at.isoformat(),
    }


def _paper_trade_from_mapping(payload: Mapping[str, JsonValue]) -> PaperTrade:
    occurred_at = datetime.fromisoformat(str(payload.get("occurred_at", DEFAULT_NOW.isoformat())))
    return PaperTrade(
        order_intent_id=UUID(str(payload["order_intent_id"])),
        side=OrderSide(str(payload["side"])),
        quantity=_decimal(payload["quantity"]),
        price=_decimal(payload["price"]),
        fee_paid=_decimal(payload.get("fee_paid", "0")),
        occurred_at=occurred_at,
    )


def _decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _latest_spread(latest: PaperTradingCycleResult | None) -> Decimal | None:
    if latest is None:
        return None
    return latest.snapshot.order_book_metrics.spread


def _unrealized_pnl(status: PaperStatusResponse) -> str:
    portfolio = status.portfolio
    price = status.current_btc_price or portfolio.average_entry_price
    if portfolio.base_quantity <= DECIMAL_ZERO:
        return "0"
    return str((price - portfolio.average_entry_price) * portfolio.base_quantity)


def _risk_halts(status: PaperStatusResponse) -> tuple[str, ...]:
    if status.blocked_reason != "not blocked":
        return (status.blocked_reason,)
    return ("none",)


def _approval_block_reason(
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
) -> str:
    if status.kill_switch_active:
        return "paper kill switch is active; use Reset Emergency Stop"
    if status.paused:
        return "paper bot is paused"
    if latest is None:
        return "no paper cycle has run"
    if latest.risk_decision_status == "rejected":
        return "Risk Management Engine rejected this recommendation"
    if not latest.executed:
        return latest.skipped_reason or "latest recommendation is not executable"
    return "latest simulated trade is not risk-approved"


def _risk_amount(*, entry: Decimal, stop: Decimal | None, quantity: Decimal) -> Decimal:
    if stop is None or quantity <= DECIMAL_ZERO:
        return DECIMAL_ZERO
    return abs(entry - stop) * quantity


def _reward_risk(
    *,
    entry: Decimal,
    stop: Decimal | None,
    target: Decimal | None,
) -> Decimal | None:
    if stop is None or target is None:
        return None
    risk = abs(entry - stop)
    if risk <= DECIMAL_ZERO:
        return None
    return abs(target - entry) / risk


def _latest_time(engine: PaperTradingEngine) -> datetime:
    return engine.cycles[-1].snapshot.received_at if engine.cycles else DEFAULT_NOW


def _str(value: object | None) -> str:
    return "not_available" if value is None else str(value)


def _as_list(value: JsonValue) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def _as_text_list(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _as_mapping(value: JsonValue) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise PaperDashboardActionError("dashboard state is malformed")
    return value
