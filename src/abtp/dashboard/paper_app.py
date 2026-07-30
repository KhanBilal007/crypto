"""Paper-only local dashboard state and safe actions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from abtp.api import PaperAPIRequestContext, PaperAPIRole, PaperStatusResponse, PaperTradingAPI
from abtp.data import OrderBookMetrics, StreamHealth
from abtp.domain import Asset, AssetPair, Candle, Exchange
from abtp.domain.models import JsonValue
from abtp.paper import (
    PaperAccountConfig,
    PaperTradingAccount,
    PaperTradingConfig,
    PaperTradingEngine,
)
from abtp.paper.engine import PaperMarketSnapshot, PaperTradingCycleResult
from abtp.risk import RiskPolicy
from abtp.strategies import MinRiskSpotStrategyV1

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


@dataclass(slots=True)
class PaperDashboardController:
    """Local paper dashboard controller with no live execution authority."""

    engine: PaperTradingEngine
    api: PaperTradingAPI
    report_path: str = "docs/paper_trading_status_report.md"
    events: list[PaperDashboardEvent] = field(default_factory=list)

    def state(self) -> dict[str, JsonValue]:
        """Return a browser-safe dashboard state payload."""

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
        return {
            "mode": "PAPER MODE",
            "safe_mode": True,
            "live_trading_enabled": False,
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
            },
            "logs": list(event.as_dict() for event in self.events),
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

    def approve_paper_trade(self, *, reason: str = "operator approved paper trade") -> None:
        """Record approval for a simulated risk-approved paper trade only."""

        state = self.state()
        controls = _as_mapping(state["controls"])
        if controls.get("can_approve_paper_trade") is not True:
            raise PaperDashboardActionError(str(controls.get("approval_block_reason")))
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type=DashboardAction.APPROVE_PAPER_TRADE.value,
                message="Operator approved a simulated paper trade only.",
                reason=reason,
                occurred_at=_latest_time(self.engine),
            ),
        )

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

    def resume(self, *, reason: str = "operator resumed paper bot") -> None:
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

    def create_live_order(self, *_args: object, **_kwargs: object) -> None:
        raise PaperDashboardActionError("paper dashboard cannot create live orders")

    def enable_live_trading(self, *_args: object, **_kwargs: object) -> None:
        raise PaperDashboardActionError("paper dashboard cannot enable live trading")


def build_default_paper_dashboard_controller(
    *,
    risk_policy: RiskPolicy | None = None,
) -> PaperDashboardController:
    """Create a deterministic local controller for dashboard development/testing."""

    engine = PaperTradingEngine(
        strategy=MinRiskSpotStrategyV1(),
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
    for index, close in enumerate(("100", "101", "102", "104")):
        engine.on_market_update(_snapshot(index, Decimal(close)))
    controller = PaperDashboardController(
        engine=engine,
        api=PaperTradingAPI(engine),
        events=_initial_events(engine),
    )
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


def _snapshot(index: int, close: Decimal, *, stale: bool = False) -> PaperMarketSnapshot:
    candle = _candle(index, close)
    received_at = candle.closed_at + timedelta(seconds=1)
    return PaperMarketSnapshot(
        candle=candle,
        order_book_metrics=OrderBookMetrics(
            best_bid=candle.close - Decimal("0.01"),
            best_ask=candle.close + Decimal("0.01"),
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
            last_message_at=received_at,
            latency_ms=2000 if stale else 10,
            stale_after=timedelta(seconds=30),
        ),
        received_at=received_at,
    )


def _candle(index: int, close: Decimal) -> Candle:
    opened_at = DEFAULT_NOW + timedelta(hours=index)
    return Candle(
        exchange=Exchange("sandbox"),
        pair=PAIR,
        interval="1h",
        opened_at=opened_at,
        closed_at=opened_at + timedelta(hours=1),
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
    halts: list[str] = []
    if status.paused:
        halts.append("paper bot paused")
    if status.kill_switch_active:
        halts.append("paper kill switch active")
    if status.blocked_reason != "not blocked":
        halts.append(status.blocked_reason)
    return tuple(halts) or ("none",)


def _approval_block_reason(
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
) -> str:
    if status.kill_switch_active:
        return "paper kill switch is active"
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


def _as_mapping(value: JsonValue) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise PaperDashboardActionError("dashboard state is malformed")
    return value
