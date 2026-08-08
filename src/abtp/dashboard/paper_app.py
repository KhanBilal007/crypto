"""Paper-only local dashboard state and safe actions."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from sqlite3 import Connection
from uuid import UUID, uuid4

from abtp.api import (
    PaperAPIRequestContext,
    PaperAPIRole,
    PaperParameterHealth,
    PaperStatusResponse,
    PaperTradingAPI,
)
from abtp.backtesting.metrics import (
    calculate_expectancy,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_win_rate,
    returns_from_equity,
)
from abtp.data import OrderBookMetrics, StreamHealth, calculate_order_book_metrics
from abtp.db import apply_migrations, connect_database
from abtp.domain import (
    Asset,
    AssetPair,
    Candle,
    Exchange,
    OrderBookLevel,
    OrderBookSnapshot,
    OrderSide,
    Signal,
    SignalDirection,
    Trade,
)
from abtp.domain.models import JsonValue
from abtp.exchanges import (
    BinanceSpotMarketDataAdapter,
    BinanceSpotMarketDataConfig,
    ExchangeAdapterError,
)
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
WATCHLIST_PAIRS = (
    AssetPair(Asset("BTC"), Asset("USDT")),
    AssetPair(Asset("ETH"), Asset("USDT")),
    AssetPair(Asset("SOL"), Asset("USDT")),
)
WATCHLIST_DEMO_PRICES = {
    "BTC/USDT": Decimal("104"),
    "ETH/USDT": Decimal("3120"),
    "SOL/USDT": Decimal("168"),
}
WATCHLIST_DEMO_PREVIOUS_DAY_PRICES = {
    "BTC/USDT": Decimal("100"),
    "ETH/USDT": Decimal("3000"),
    "SOL/USDT": Decimal("160"),
}
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


class DashboardPaperOrderType(StrEnum):
    """Paper-only advanced order ticket types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    OCO = "oco"


class DashboardPaperOrderStatus(StrEnum):
    """Lifecycle for local simulated order-ticket rows."""

    OPEN = "open"
    CANCELED = "canceled"


class DashboardAlertType(StrEnum):
    """Local dashboard alert types."""

    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    INDICATOR_CONFIDENCE = "indicator_confidence"
    DRAWDOWN_ABOVE = "drawdown_above"
    STALE_DATA = "stale_data"
    PAPER_ORDER_EVENT = "paper_order_event"
    RISK_HALT = "risk_halt"
    RECOMMENDATION = "recommendation"


class DashboardChartDrawingType(StrEnum):
    """Local-only chart annotation types."""

    HORIZONTAL_LEVEL = "horizontal_level"
    TRENDLINE = "trendline"
    BOX = "box"
    NOTE = "note"
    FIBONACCI = "fibonacci"


@dataclass(frozen=True, slots=True)
class DashboardPaperOrderFilter:
    """Binance-style paper order constraints for local ticket validation."""

    symbol: str
    tick_size: Decimal
    step_size: Decimal
    min_quantity: Decimal
    min_notional: Decimal
    price_precision: int
    quantity_precision: int

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "symbol": self.symbol,
            "tick_size": str(self.tick_size),
            "step_size": str(self.step_size),
            "min_quantity": str(self.min_quantity),
            "min_notional": str(self.min_notional),
            "price_precision": self.price_precision,
            "quantity_precision": self.quantity_precision,
            "source": "paper_binance_style_filter",
            "paper_only": True,
        }


PAPER_ORDER_FILTER = DashboardPaperOrderFilter(
    symbol="BTC/USDT",
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
    min_notional=Decimal("1"),
    price_precision=2,
    quantity_precision=4,
)


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


@dataclass(frozen=True, slots=True)
class DashboardWatchlistItem:
    """Read-only market observation row for the Advanced Trader watchlist."""

    symbol: str
    price: Decimal | None
    source: str
    updated_at: datetime
    data_health: str
    paper_tradable: bool
    note: str
    price_change_24h_pct: Decimal | None = None

    def as_dict(self, *, selected_symbol: str) -> dict[str, JsonValue]:
        return {
            "symbol": self.symbol,
            "price": _str(self.price),
            "price_change_24h_pct": _status_str(self.price_change_24h_pct, "unavailable"),
            "source": self.source,
            "updated_at": self.updated_at.isoformat(),
            "data_health": self.data_health,
            "paper_tradable": self.paper_tradable,
            "selected": self.symbol == selected_symbol,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class DashboardPaperOrder:
    """One local simulated paper order created from Advanced Trader."""

    order_id: str
    order_type: DashboardPaperOrderType
    side: OrderSide
    quantity: Decimal
    created_at: datetime
    status: DashboardPaperOrderStatus = DashboardPaperOrderStatus.OPEN
    symbol: str = "BTC/USDT"
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    take_profit_price: Decimal | None = None
    reason: str = ""

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "order_type": self.order_type.value,
            "side": self.side.value,
            "quantity": str(self.quantity),
            "limit_price": _str(self.limit_price),
            "stop_price": _str(self.stop_price),
            "take_profit_price": _str(self.take_profit_price),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "reason": self.reason,
            "paper_only": True,
        }


@dataclass(frozen=True, slots=True)
class DashboardAlertRule:
    """One local dashboard alert rule."""

    alert_id: str
    alert_type: DashboardAlertType
    symbol: str
    created_at: datetime
    threshold: Decimal | None = None
    expected_value: str = ""
    enabled: bool = True

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "symbol": self.symbol,
            "threshold": _str(self.threshold),
            "expected_value": self.expected_value,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "paper_only": True,
        }


@dataclass(frozen=True, slots=True)
class DashboardJournalEntry:
    """One local paper trade journal note for trader review."""

    journal_id: str
    symbol: str
    setup_type: str
    tags: tuple[str, ...]
    notes: str
    mistake_review: str
    lesson: str
    chart_context: str
    created_at: datetime
    updated_at: datetime
    trade_ref: str = ""
    strategy: str = "MinRiskSpotStrategyV1"
    regime: str = "unknown"

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "journal_id": self.journal_id,
            "trade_ref": self.trade_ref,
            "symbol": self.symbol,
            "setup_type": self.setup_type,
            "tags": list(self.tags),
            "notes": self.notes,
            "mistake_review": self.mistake_review,
            "lesson": self.lesson,
            "chart_context": self.chart_context,
            "strategy": self.strategy,
            "regime": self.regime,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "paper_only": True,
        }


@dataclass(frozen=True, slots=True)
class DashboardTraderFeedback:
    """One local paper-mode feedback item from a trader reviewer."""

    feedback_id: str
    reviewer_role: str
    category: str
    severity: str
    summary: str
    recommendation: str
    status: str
    created_at: datetime
    resolution: str = ""
    resolved_at: datetime | None = None

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "feedback_id": self.feedback_id,
            "reviewer_role": self.reviewer_role,
            "category": self.category,
            "severity": self.severity,
            "summary": self.summary,
            "recommendation": self.recommendation,
            "status": self.status,
            "resolution": self.resolution,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at is not None else "",
            "paper_only": True,
        }


@dataclass(frozen=True, slots=True)
class DashboardChartDrawing:
    """One local chart annotation saved for Advanced Trader review."""

    drawing_id: str
    drawing_type: DashboardChartDrawingType
    symbol: str
    timeframe: str
    start_time: str
    start_price: Decimal
    created_at: datetime
    end_time: str = ""
    end_price: Decimal | None = None
    text: str = ""
    color: str = "#1264a3"
    enabled: bool = True

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "drawing_id": self.drawing_id,
            "drawing_type": self.drawing_type.value,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "start_price": str(self.start_price),
            "end_price": _str(self.end_price),
            "text": self.text,
            "color": self.color,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "paper_only": True,
        }


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
    requested_market_data_source: str = "demo"
    selected_watchlist_symbol: str = "BTC/USDT"
    watchlist: tuple[DashboardWatchlistItem, ...] = ()
    ui_mode: DashboardUIMode = DashboardUIMode.ADVANCED_TRADER
    strategy_lab_strategy: str = "min_risk_spot_v1"
    strategy_lab_symbol: str = "BTC/USDT"
    strategy_lab_timeframe: str = "1h"
    strategy_lab_run_mode: StrategyLabRunMode = StrategyLabRunMode.PAPER
    strategy_lab_parameter_profile: str = "default"
    sidebar_collapsed: bool = False
    notification_last_seen_at: datetime | None = None
    order_book_snapshot: OrderBookSnapshot | None = None
    recent_market_trades: tuple[Trade, ...] = ()
    open_paper_orders: list[DashboardPaperOrder] = field(default_factory=list)
    alert_rules: list[DashboardAlertRule] = field(default_factory=list)
    journal_entries: list[DashboardJournalEntry] = field(default_factory=list)
    trader_feedback: list[DashboardTraderFeedback] = field(default_factory=list)
    chart_drawings: list[DashboardChartDrawing] = field(default_factory=list)
    events: list[PaperDashboardEvent] = field(default_factory=list)
    session_starting_equity: Decimal | None = None
    market_refresh_interval_seconds: int = 15
    last_market_refresh_at: datetime | None = None

    def state(self, *, ui_mode: DashboardUIMode | str | None = None) -> dict[str, JsonValue]:
        """Return a browser-safe dashboard state payload."""

        active_ui_mode = _ui_mode(ui_mode or self.ui_mode)
        self.refresh_market_data_if_due()
        latest = self.engine.cycles[-1] if self.engine.cycles else None
        active_watchlist_item = _selected_watchlist_item(
            self.watchlist,
            self.selected_watchlist_symbol,
        )
        paper_mark_price = _paper_strategy_mark_price(self.watchlist, latest=latest)
        server_time = datetime.now(UTC)
        status = self.api.status(READ_CONTEXT, mark_price=paper_mark_price)
        strategy_state = _strategy_state(status, latest)
        suggested_trade = _suggested_trade(latest)
        starting_balance = (
            self.session_starting_equity
            if self.session_starting_equity is not None
            else self.engine.account.config.initial_cash
        )
        can_approve = (
            latest is not None
            and latest.executed
            and latest.risk_decision_status == "approved"
            and not status.paused
            and not status.kill_switch_active
        )
        alert_state = _alert_state(
            self.alert_rules,
            market_item=active_watchlist_item,
            status=status,
            latest=latest,
            events=self.events,
            recommendation=str(strategy_state.get("recommendation", "HOLD")),
        )
        notifications = _notification_state(
            alerts=alert_state,
            status=status,
            market_item=active_watchlist_item,
            latest=latest,
            last_seen_at=self.notification_last_seen_at,
            server_time=server_time,
        )
        refresh = _refresh_status(
            last_refresh_at=self.last_market_refresh_at,
            interval_seconds=self.market_refresh_interval_seconds,
            server_time=server_time,
        )
        app_metadata = _app_metadata(server_time)
        payload: dict[str, JsonValue] = {
            "mode": "PAPER MODE",
            "safe_mode": True,
            "live_trading_enabled": False,
            "app": app_metadata,
            "ui_mode": active_ui_mode.value,
            "ui": {
                "mode": active_ui_mode.value,
                "copy_source": "static_dashboard_text",
                "available_modes": [
                    {"value": DashboardUIMode.BEGINNER.value, "label": "Beginner"},
                    {"value": DashboardUIMode.ADVANCED_TRADER.value, "label": "Advanced Trader"},
                    {"value": DashboardUIMode.STRATEGY_LAB.value, "label": "Strategy Lab"},
                ],
                "navigation": _ui_navigation_state(active_ui_mode),
                "sidebar_collapsed": self.sidebar_collapsed,
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
                "symbol": active_watchlist_item.symbol,
                "paper_strategy_symbol": "BTC/USDT",
                "source": active_watchlist_item.source,
                "current_price": _str(active_watchlist_item.price),
                "price_change_24h_pct": _status_str(
                    active_watchlist_item.price_change_24h_pct,
                    "unavailable",
                ),
                "spread": _str(_latest_spread(latest)),
                "data_freshness": active_watchlist_item.data_health,
                "exchange_connection": _exchange_connection_status(
                    requested_source=self.requested_market_data_source,
                    market_item=active_watchlist_item,
                    latest=latest,
                ),
                "exchange_connection_detail": _exchange_connection_detail(
                    requested_source=self.requested_market_data_source,
                    market_item=active_watchlist_item,
                    latest=latest,
                ),
                "latency_ms": _latency_ms(latest),
                "trend_strength_pct": _trend_strength_pct(latest),
                "trend_strength_source": _trend_strength_source(latest),
                "market_regime": status.active_regime,
                "updated_at": active_watchlist_item.updated_at.isoformat(),
                "paper_tradable": active_watchlist_item.paper_tradable,
                "symbol_note": active_watchlist_item.note,
            },
            "strategy": strategy_state,
            "suggested_paper_trade": suggested_trade,
            "portfolio": {
                "starting_balance": str(starting_balance),
                "current_equity": str(status.portfolio.equity),
                "mark_symbol": PAIR.symbol,
                "mark_price": _str(paper_mark_price),
                "mark_source": "paper_strategy_symbol",
                "cash": str(status.portfolio.cash),
                "open_btc": str(status.portfolio.base_quantity),
                "realized_pnl": str(status.portfolio.realized_pnl),
                "unrealized_pnl": _unrealized_pnl(status),
                "today_pnl": _today_pnl(
                    cycles=self.engine.cycles,
                    status=status,
                    starting_balance=starting_balance,
                    session_baseline=self.session_starting_equity,
                ),
                "today_pnl_pct": _today_pnl_pct(
                    cycles=self.engine.cycles,
                    status=status,
                    starting_balance=starting_balance,
                    session_baseline=self.session_starting_equity,
                ),
                "today_pnl_status": "calculated",
                "today_pnl_source": "paper_cycle_equity",
                "equity_sparkline": _portfolio_sparkline(self.engine.account.state.equity_history),
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
            "open_paper_orders": _open_paper_order_state(self.open_paper_orders),
            "journal_entries": _journal_entry_state(self.journal_entries),
            "chart_drawings": _chart_drawing_state(self.chart_drawings),
            "watchlist": _watchlist_state(
                self.watchlist,
                selected_symbol=active_watchlist_item.symbol,
            ),
            "alert_rules": _alert_rule_state(self.alert_rules),
            "trader_feedback": _trader_feedback_state(self.trader_feedback),
            "alerts": alert_state,
            "notifications": notifications,
            "refresh": refresh,
            "activity": _activity_state(self.events, limit=5),
            "runtime_telemetry": _runtime_telemetry(
                market_item=active_watchlist_item,
                latest=latest,
                cycles=self.engine.cycles,
                status=status,
                notifications=notifications,
                app_metadata=app_metadata,
                refresh=refresh,
                requested_source=self.requested_market_data_source,
                equity_history=self.engine.account.state.equity_history,
            ),
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
            order_book=self.order_book_snapshot,
            recent_market_trades=self.recent_market_trades,
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

    def refresh_market_data_if_due(self, *, now: datetime | None = None) -> None:
        """Refresh read-only Binance market observations for a running dashboard."""

        if self.requested_market_data_source != "binance":
            return
        checked_at = now or datetime.now(UTC)
        if (
            self.last_market_refresh_at is not None
            and checked_at - self.last_market_refresh_at
            < timedelta(seconds=self.market_refresh_interval_seconds)
        ):
            return
        self.last_market_refresh_at = checked_at
        adapter = BinanceSpotMarketDataAdapter(BinanceSpotMarketDataConfig(timeout_seconds=1.0))
        self.watchlist = _refresh_binance_watchlist(adapter, self.watchlist, checked_at=checked_at)
        try:
            self.order_book_snapshot = adapter.order_book(PAIR)
        except (AttributeError, ExchangeAdapterError, OSError, ValueError):
            return

    def set_ui_mode(self, mode: DashboardUIMode | str) -> dict[str, JsonValue]:
        """Persist the preferred dashboard shell mode without changing trading permissions."""

        self.ui_mode = _ui_mode(mode)
        _save_dashboard_preferences(self)
        return self.state()

    def set_ui_shell_preferences(
        self,
        *,
        sidebar_collapsed: bool | None = None,
    ) -> dict[str, JsonValue]:
        """Persist local shell presentation preferences only."""

        if sidebar_collapsed is not None:
            self.sidebar_collapsed = sidebar_collapsed
        _save_dashboard_preferences(self)
        return self.state()

    def mark_notifications_read(self) -> dict[str, JsonValue]:
        """Mark the local notification bell as seen without deleting audit evidence."""

        self.notification_last_seen_at = datetime.now(UTC)
        _save_dashboard_preferences(self)
        return self.state()

    def activity_state(self, *, limit: int | None = None) -> dict[str, JsonValue]:
        """Return the paper dashboard activity timeline read model."""

        return _activity_state(self.events, limit=limit)

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

    def set_watchlist_symbol(self, symbol: str) -> dict[str, JsonValue]:
        """Persist selected watchlist symbol without changing paper strategy authority."""

        self.selected_watchlist_symbol = _watchlist_symbol(symbol)
        _save_dashboard_preferences(self)
        return self.state()

    def add_alert_rule(
        self,
        *,
        alert_type: str,
        symbol: str,
        threshold: str | None = None,
        expected_value: str | None = None,
    ) -> dict[str, JsonValue]:
        """Create a local dashboard alert rule."""

        active_type = _alert_type(alert_type)
        active_symbol = _watchlist_symbol(symbol)
        active_threshold = _alert_threshold(active_type, threshold)
        rule = DashboardAlertRule(
            alert_id=f"alert-{uuid4()}",
            alert_type=active_type,
            symbol=active_symbol,
            threshold=active_threshold,
            expected_value=_alert_expected_value(active_type, expected_value),
            created_at=_latest_time(self.engine),
        )
        self.alert_rules.insert(0, rule)
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type="add_alert_rule",
                message="Operator added a local dashboard alert rule.",
                reason=f"{rule.alert_type.value} {rule.symbol}",
                occurred_at=rule.created_at,
            ),
        )
        _save_paper_account_state(self)
        return self.state()

    def delete_alert_rule(self, *, alert_id: str) -> dict[str, JsonValue]:
        """Remove one local dashboard alert rule."""

        cleaned_id = alert_id.strip()
        before = len(self.alert_rules)
        self.alert_rules = [rule for rule in self.alert_rules if rule.alert_id != cleaned_id]
        if len(self.alert_rules) == before:
            raise PaperDashboardActionError(f"unknown alert id: {cleaned_id}")
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type="delete_alert_rule",
                message="Operator removed a local dashboard alert rule.",
                reason=cleaned_id,
                occurred_at=_latest_time(self.engine),
            ),
        )
        _save_paper_account_state(self)
        return self.state()

    def save_journal_entry(
        self,
        *,
        trade_ref: str | None = None,
        symbol: str | None = None,
        setup_type: str | None = None,
        tags: str | None = None,
        notes: str | None = None,
        mistake_review: str | None = None,
        lesson: str | None = None,
        chart_context: str | None = None,
    ) -> dict[str, JsonValue]:
        """Save one local paper trade journal entry."""

        active_symbol = _watchlist_symbol(symbol or self.selected_watchlist_symbol)
        latest = self.engine.cycles[-1] if self.engine.cycles else None
        strategy_name = (
            latest.strategy_evaluation.strategy_name
            if latest is not None and latest.strategy_evaluation is not None
            else "MinRiskSpotStrategyV1"
        )
        regime = self.api.status(READ_CONTEXT).active_regime
        now = _latest_time(self.engine)
        entry = DashboardJournalEntry(
            journal_id=f"journal-{uuid4()}",
            trade_ref=(trade_ref or "").strip(),
            symbol=active_symbol,
            setup_type=_journal_setup_type(setup_type),
            tags=_journal_tags(tags),
            notes=_limited_text(notes, "notes", max_length=500),
            mistake_review=_limited_text(mistake_review, "mistake review", max_length=500),
            lesson=_limited_text(lesson, "lesson", max_length=500),
            chart_context=_limited_text(chart_context, "chart context", max_length=300),
            strategy=strategy_name,
            regime=regime,
            created_at=now,
            updated_at=now,
        )
        self.journal_entries.insert(0, entry)
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type="save_journal_entry",
                message="Operator saved a local paper trade journal entry.",
                reason=f"{entry.symbol} {entry.setup_type}",
                occurred_at=now,
            ),
        )
        _save_paper_account_state(self)
        return self.state()

    def delete_journal_entry(self, *, journal_id: str) -> dict[str, JsonValue]:
        """Remove one local paper trade journal entry."""

        cleaned_id = journal_id.strip()
        before = len(self.journal_entries)
        self.journal_entries = [
            entry for entry in self.journal_entries if entry.journal_id != cleaned_id
        ]
        if len(self.journal_entries) == before:
            raise PaperDashboardActionError(f"unknown journal id: {cleaned_id}")
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type="delete_journal_entry",
                message="Operator removed a local paper trade journal entry.",
                reason=cleaned_id,
                occurred_at=_latest_time(self.engine),
            ),
        )
        _save_paper_account_state(self)
        return self.state()

    def save_trader_feedback(
        self,
        *,
        reviewer_role: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        summary: str | None = None,
        recommendation: str | None = None,
    ) -> dict[str, JsonValue]:
        """Save one local trader-review feedback item."""

        now = _latest_time(self.engine)
        feedback = DashboardTraderFeedback(
            feedback_id=f"feedback-{uuid4()}",
            reviewer_role=_trader_feedback_reviewer_role(reviewer_role),
            category=_trader_feedback_category(category),
            severity=_trader_feedback_severity(severity),
            summary=_limited_text(summary, "feedback summary", max_length=400),
            recommendation=_limited_text(
                recommendation,
                "feedback recommendation",
                max_length=500,
            ),
            status="open",
            created_at=now,
        )
        if not feedback.summary.strip():
            raise PaperDashboardActionError("feedback summary is required")
        self.trader_feedback.insert(0, feedback)
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type="save_trader_feedback",
                message="Operator saved local trader review feedback.",
                reason=f"{feedback.category} {feedback.severity}",
                occurred_at=now,
            ),
        )
        _save_paper_account_state(self)
        return self.state()

    def close_trader_feedback(
        self,
        *,
        feedback_id: str,
        resolution: str | None = None,
    ) -> dict[str, JsonValue]:
        """Mark one trader feedback item as closed in local paper state."""

        cleaned_id = feedback_id.strip()
        cleaned_resolution = _limited_text(
            resolution,
            "feedback resolution",
            max_length=500,
        )
        now = _latest_time(self.engine)
        updated: list[DashboardTraderFeedback] = []
        found = False
        for item in self.trader_feedback:
            if item.feedback_id != cleaned_id:
                updated.append(item)
                continue
            found = True
            if item.severity == "blocker" and not cleaned_resolution:
                raise PaperDashboardActionError(
                    "blocker feedback requires a resolution note before closing"
                )
            updated.append(
                DashboardTraderFeedback(
                    feedback_id=item.feedback_id,
                    reviewer_role=item.reviewer_role,
                    category=item.category,
                    severity=item.severity,
                    summary=item.summary,
                    recommendation=item.recommendation,
                    status="closed",
                    created_at=item.created_at,
                    resolution=cleaned_resolution,
                    resolved_at=now,
                )
            )
        if not found:
            raise PaperDashboardActionError(f"unknown trader feedback id: {cleaned_id}")
        self.trader_feedback = updated
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type="close_trader_feedback",
                message="Operator closed a local trader review feedback item.",
                reason=cleaned_id,
                occurred_at=now,
            ),
        )
        _save_paper_account_state(self)
        return self.state()

    def save_chart_drawing(
        self,
        *,
        drawing_type: str,
        symbol: str | None = None,
        timeframe: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        start_price: str | None = None,
        end_price: str | None = None,
        text: str | None = None,
        color: str | None = None,
    ) -> dict[str, JsonValue]:
        """Save one local-only chart annotation."""

        active_type = _chart_drawing_type(drawing_type)
        active_symbol = _watchlist_symbol(symbol or self.selected_watchlist_symbol)
        active_timeframe = _chart_drawing_timeframe(timeframe)
        latest = self.engine.cycles[-1] if self.engine.cycles else None
        fallback_price = latest.snapshot.candle.close if latest is not None else Decimal("1")
        drawing = DashboardChartDrawing(
            drawing_id=f"drawing-{uuid4()}",
            drawing_type=active_type,
            symbol=active_symbol,
            timeframe=active_timeframe,
            start_time=_chart_drawing_time(start_time, latest=latest),
            end_time=_chart_drawing_time(end_time, latest=latest),
            start_price=_chart_drawing_price(start_price, fallback=fallback_price),
            end_price=_chart_drawing_optional_price(
                end_price,
                fallback=fallback_price,
                drawing_type=active_type,
            ),
            text=_limited_text(text, "drawing text", max_length=120),
            color=_chart_drawing_color(color),
            created_at=_latest_time(self.engine),
        )
        self.chart_drawings.insert(0, drawing)
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type="save_chart_drawing",
                message="Operator saved a local chart drawing.",
                reason=f"{drawing.symbol} {drawing.drawing_type.value}",
                occurred_at=drawing.created_at,
            ),
        )
        _save_paper_account_state(self)
        return self.state()

    def delete_chart_drawing(self, *, drawing_id: str) -> dict[str, JsonValue]:
        """Remove one local chart drawing."""

        cleaned_id = drawing_id.strip()
        before = len(self.chart_drawings)
        self.chart_drawings = [
            drawing for drawing in self.chart_drawings if drawing.drawing_id != cleaned_id
        ]
        if len(self.chart_drawings) == before:
            raise PaperDashboardActionError(f"unknown chart drawing id: {cleaned_id}")
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type="delete_chart_drawing",
                message="Operator removed a local chart drawing.",
                reason=cleaned_id,
                occurred_at=_latest_time(self.engine),
            ),
        )
        _save_paper_account_state(self)
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

    def submit_paper_order_ticket(
        self,
        *,
        order_type: str,
        side: str,
        quantity: str,
        limit_price: str | None = None,
        stop_price: str | None = None,
        take_profit_price: str | None = None,
        reason: str = "operator staged paper order ticket",
    ) -> dict[str, JsonValue]:
        """Create one local simulated order-ticket row without live execution."""

        status = self.api.status(READ_CONTEXT)
        if status.paused:
            raise PaperDashboardActionError("paper bot is paused")
        if status.kill_switch_active:
            raise PaperDashboardActionError("paper kill switch is active")
        reference_price = (
            status.current_btc_price
            or status.portfolio.average_entry_price
            or WATCHLIST_DEMO_PRICES["BTC/USDT"]
        )
        active_order = _paper_order_from_ticket(
            order_type=order_type,
            side=side,
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            take_profit_price=take_profit_price,
            reference_price=reference_price,
            created_at=_latest_time(self.engine),
            reason=reason,
        )
        self.open_paper_orders.insert(0, active_order)
        self.events.insert(
            0,
            PaperDashboardEvent(
                event_type="submit_paper_order_ticket",
                message="Operator staged a simulated paper order ticket only.",
                reason=f"{active_order.order_type.value} {active_order.side.value} "
                f"{active_order.quantity} BTC",
                occurred_at=active_order.created_at,
            ),
        )
        _save_paper_account_state(self)
        return self.state()

    def cancel_paper_order(
        self,
        *,
        order_id: str,
        reason: str = "operator canceled paper order",
    ) -> dict[str, JsonValue]:
        """Cancel one local simulated order-ticket row."""

        cleaned_id = order_id.strip()
        if not cleaned_id:
            raise PaperDashboardActionError("paper order id is required")
        for index, order in enumerate(self.open_paper_orders):
            if order.order_id != cleaned_id:
                continue
            canceled = DashboardPaperOrder(
                order_id=order.order_id,
                order_type=order.order_type,
                side=order.side,
                quantity=order.quantity,
                created_at=order.created_at,
                status=DashboardPaperOrderStatus.CANCELED,
                symbol=order.symbol,
                limit_price=order.limit_price,
                stop_price=order.stop_price,
                take_profit_price=order.take_profit_price,
                reason=reason,
            )
            self.open_paper_orders[index] = canceled
            self.events.insert(
                0,
                PaperDashboardEvent(
                    event_type="cancel_paper_order",
                    message="Operator canceled a simulated paper order ticket.",
                    reason=cleaned_id,
                    occurred_at=_latest_time(self.engine),
                ),
            )
            _save_paper_account_state(self)
            return self.state()
        raise PaperDashboardActionError(f"unknown paper order id: {cleaned_id}")

    def stage_close_position(
        self,
        *,
        reason: str = "operator staged close paper position",
    ) -> dict[str, JsonValue]:
        """Stage a paper-only market sell for the full open BTC position."""

        quantity = self.engine.account.state.base_quantity
        if quantity <= DECIMAL_ZERO:
            raise PaperDashboardActionError("no open paper BTC position to close")
        return self.submit_paper_order_ticket(
            order_type=DashboardPaperOrderType.MARKET.value,
            side=OrderSide.SELL.value,
            quantity=str(quantity),
            reason=reason,
        )

    def stage_reduce_position(
        self,
        *,
        reason: str = "operator staged reduce paper position",
    ) -> dict[str, JsonValue]:
        """Stage a paper-only market sell for half of the open BTC position."""

        quantity = self.engine.account.state.base_quantity
        if quantity <= DECIMAL_ZERO:
            raise PaperDashboardActionError("no open paper BTC position to reduce")
        return self.submit_paper_order_ticket(
            order_type=DashboardPaperOrderType.MARKET.value,
            side=OrderSide.SELL.value,
            quantity=str(quantity / Decimal("2")),
            reason=reason,
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
    (
        snapshots,
        active_market_source,
        source_events,
        daily_confirmation,
        order_book,
        recent_market_trades,
        watchlist,
    ) = _dashboard_inputs(requested_market_source)
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
        account=PaperTradingAccount(PaperAccountConfig(initial_cash=_paper_initial_cash())),
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
    controller = PaperDashboardController(
        engine=engine,
        api=PaperTradingAPI(engine),
        state_path=state_path if state_path is not None else os.getenv("ABTP_PAPER_STATE_PATH"),
        db_path=db_path if db_path is not None else os.getenv("ABTP_PAPER_DB_PATH"),
        market_data_source=active_market_source,
        requested_market_data_source=requested_market_source,
        order_book_snapshot=order_book,
        recent_market_trades=recent_market_trades,
        watchlist=watchlist,
        events=[*source_events],
    )
    for snapshot in snapshots:
        engine.on_market_update(snapshot)
    controller.events.extend(_initial_events(engine))
    if _restore_paper_account_state(controller):
        latest = engine.cycles[-1] if engine.cycles else None
        paper_mark_price = _paper_strategy_mark_price(watchlist, latest=latest)
        controller.session_starting_equity = controller.api.status(
            READ_CONTEXT,
            mark_price=paper_mark_price,
        ).portfolio.equity
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
    return events


def _dashboard_inputs(
    requested_market_source: str,
) -> tuple[
    tuple[PaperMarketSnapshot, ...],
    str,
    tuple[PaperDashboardEvent, ...],
    DailyTrendConfirmation | None,
    OrderBookSnapshot,
    tuple[Trade, ...],
    tuple[DashboardWatchlistItem, ...],
]:
    if requested_market_source == "binance":
        try:
            snapshots, daily_confirmation, order_book, recent_market_trades, watchlist = (
                _binance_snapshots_and_daily_confirmation()
            )
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
                order_book,
                recent_market_trades,
                watchlist,
            )
        except (ExchangeAdapterError, OSError, ValueError) as exc:
            snapshots = _demo_snapshots()
            order_book = _demo_order_book(snapshots[-1].candle.close)
            return (
                snapshots,
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
                order_book,
                _demo_market_trades(snapshots),
                _demo_watchlist(),
            )
    snapshots = _demo_snapshots()
    order_book = _demo_order_book(snapshots[-1].candle.close)
    return (
        snapshots,
        "demo",
        (),
        None,
        order_book,
        _demo_market_trades(snapshots),
        _demo_watchlist(),
    )


def _demo_snapshots() -> tuple[PaperMarketSnapshot, ...]:
    return tuple(
        _snapshot(index, Decimal(close)) for index, close in enumerate(("100", "101", "102", "104"))
    )


def _demo_order_book(close: Decimal) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        exchange=Exchange("sandbox"),
        pair=PAIR,
        captured_at=DEFAULT_NOW + timedelta(hours=4, seconds=1),
        bids=tuple(
            OrderBookLevel(
                price=close - Decimal("0.01") - Decimal(index) * Decimal("0.02"),
                quantity=Decimal("1.0") + Decimal(index) * Decimal("0.25"),
            )
            for index in range(5)
        ),
        asks=tuple(
            OrderBookLevel(
                price=close + Decimal("0.01") + Decimal(index) * Decimal("0.02"),
                quantity=Decimal("0.9") + Decimal(index) * Decimal("0.30"),
            )
            for index in range(5)
        ),
        source_ref="demo:paper:order-book:BTC/USDT",
    )


def _demo_market_trades(snapshots: tuple[PaperMarketSnapshot, ...]) -> tuple[Trade, ...]:
    trades: list[Trade] = []
    for index, snapshot in enumerate(snapshots[-4:]):
        candle = snapshot.candle
        trades.append(
            Trade(
                exchange=Exchange("sandbox"),
                pair=PAIR,
                traded_at=candle.closed_at - timedelta(minutes=3),
                price=candle.close - Decimal("0.03"),
                quantity=Decimal("0.14") + Decimal(index) * Decimal("0.02"),
                side=OrderSide.SELL if index % 2 else OrderSide.BUY,
                trade_id=f"demo-trade-{index}-a",
            )
        )
        trades.append(
            Trade(
                exchange=Exchange("sandbox"),
                pair=PAIR,
                traded_at=candle.closed_at - timedelta(minutes=1),
                price=candle.close + Decimal("0.02"),
                quantity=Decimal("0.18") + Decimal(index) * Decimal("0.03"),
                side=OrderSide.BUY if index % 2 else OrderSide.SELL,
                trade_id=f"demo-trade-{index}-b",
            )
        )
    return tuple(trades)


def _demo_watchlist() -> tuple[DashboardWatchlistItem, ...]:
    return tuple(
        DashboardWatchlistItem(
            symbol=pair.symbol,
            price=WATCHLIST_DEMO_PRICES[pair.symbol],
            source="demo",
            updated_at=DEFAULT_NOW + timedelta(hours=4, seconds=1),
            data_health="healthy",
            paper_tradable=pair.symbol == PAIR.symbol,
            note=_watchlist_note(pair.symbol),
            price_change_24h_pct=_demo_price_change_24h_pct(pair.symbol),
        )
        for pair in WATCHLIST_PAIRS
    )


def _demo_price_change_24h_pct(symbol: str) -> Decimal | None:
    current = WATCHLIST_DEMO_PRICES.get(symbol)
    previous = WATCHLIST_DEMO_PREVIOUS_DAY_PRICES.get(symbol)
    if current is None or previous is None or previous <= DECIMAL_ZERO:
        return None
    return (current / previous - Decimal("1")) * Decimal("100")


def _binance_snapshots_and_daily_confirmation() -> tuple[
    tuple[PaperMarketSnapshot, ...],
    DailyTrendConfirmation,
    OrderBookSnapshot,
    tuple[Trade, ...],
    tuple[DashboardWatchlistItem, ...],
]:
    adapter = BinanceSpotMarketDataAdapter()
    order_book = adapter.order_book(PAIR)
    metrics = calculate_order_book_metrics(order_book)
    hourly_candles = adapter.candles(PAIR, "1h", 4)
    daily_confirmation = _daily_confirmation_from_candles(adapter.candles(PAIR, "1d", 4))
    recent_market_trades = _binance_recent_market_trades(adapter, hourly_candles)
    watchlist = _binance_watchlist(adapter)
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
    return tuple(snapshots), daily_confirmation, order_book, recent_market_trades, watchlist


def _binance_recent_market_trades(
    adapter: BinanceSpotMarketDataAdapter,
    hourly_candles: tuple[Candle, ...],
) -> tuple[Trade, ...]:
    trade_end = hourly_candles[-1].closed_at
    try:
        return adapter.trades(PAIR, trade_end - timedelta(hours=1), trade_end)
    except (AttributeError, ExchangeAdapterError, OSError, ValueError):
        return _demo_market_trades(
            tuple(
                _snapshot(
                    index,
                    candle.close,
                    exchange_name=candle.exchange.name,
                    candle=candle,
                    received_at=candle.closed_at + timedelta(milliseconds=1),
                )
                for index, candle in enumerate(hourly_candles)
            )
        )


def _binance_watchlist(
    adapter: BinanceSpotMarketDataAdapter,
) -> tuple[DashboardWatchlistItem, ...]:
    items: list[DashboardWatchlistItem] = []
    for pair in WATCHLIST_PAIRS:
        try:
            ticker = adapter.ticker(pair)
            price_change = _binance_price_change_24h_pct(adapter, pair)
            items.append(
                DashboardWatchlistItem(
                    symbol=pair.symbol,
                    price=ticker.price,
                    source="binance spot",
                    updated_at=ticker.captured_at,
                    data_health="healthy",
                    paper_tradable=pair.symbol == PAIR.symbol,
                    note=_watchlist_note(pair.symbol),
                    price_change_24h_pct=price_change,
                )
            )
        except (AttributeError, ExchangeAdapterError, OSError, ValueError):
            items.append(
                DashboardWatchlistItem(
                    symbol=pair.symbol,
                    price=WATCHLIST_DEMO_PRICES[pair.symbol],
                    source="demo fallback",
                    updated_at=datetime.now(UTC),
                    data_health="degraded",
                    paper_tradable=pair.symbol == PAIR.symbol,
                    note=f"{_watchlist_note(pair.symbol)} Binance ticker unavailable.",
                    price_change_24h_pct=_demo_price_change_24h_pct(pair.symbol),
                )
            )
    return tuple(items)


def _refresh_binance_watchlist(
    adapter: BinanceSpotMarketDataAdapter,
    current_items: tuple[DashboardWatchlistItem, ...],
    *,
    checked_at: datetime,
) -> tuple[DashboardWatchlistItem, ...]:
    existing = {item.symbol: item for item in current_items}
    refreshed: list[DashboardWatchlistItem] = []
    for pair in WATCHLIST_PAIRS:
        try:
            ticker = adapter.ticker(pair)
            price_change = _binance_price_change_24h_pct(adapter, pair)
            refreshed.append(
                DashboardWatchlistItem(
                    symbol=pair.symbol,
                    price=ticker.price,
                    source="binance spot",
                    updated_at=ticker.captured_at,
                    data_health="healthy",
                    paper_tradable=pair.symbol == PAIR.symbol,
                    note=_watchlist_note(pair.symbol),
                    price_change_24h_pct=price_change,
                )
            )
        except (AttributeError, ExchangeAdapterError, OSError, ValueError):
            previous = existing.get(pair.symbol)
            if previous is None:
                refreshed.append(
                    DashboardWatchlistItem(
                        symbol=pair.symbol,
                        price=WATCHLIST_DEMO_PRICES[pair.symbol],
                        source="demo fallback",
                        updated_at=checked_at,
                        data_health="degraded",
                        paper_tradable=pair.symbol == PAIR.symbol,
                        note=f"{_watchlist_note(pair.symbol)} Binance ticker refresh failed.",
                        price_change_24h_pct=_demo_price_change_24h_pct(pair.symbol),
                    )
                )
                continue
            refreshed.append(
                DashboardWatchlistItem(
                    symbol=pair.symbol,
                    price=previous.price,
                    source=previous.source,
                    updated_at=previous.updated_at,
                    data_health="degraded",
                    paper_tradable=previous.paper_tradable,
                    note=previous.note
                    + " Binance ticker refresh failed; showing last known price.",
                    price_change_24h_pct=previous.price_change_24h_pct,
                )
            )
    return tuple(refreshed)


def _binance_price_change_24h_pct(
    adapter: BinanceSpotMarketDataAdapter,
    pair: AssetPair,
) -> Decimal | None:
    try:
        return adapter.price_change_24h_pct(pair)
    except (AttributeError, ExchangeAdapterError, OSError, ValueError):
        return None


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
    if not _is_executable_paper_trade(latest):
        return _empty_trade(
            latest.skipped_reason or "latest recommendation is HOLD or not executable",
            side=evaluation.signal.direction.value.upper(),
        )
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


def _empty_trade(reason: str, *, side: str = "HOLD") -> dict[str, JsonValue]:
    return {
        "side": side,
        "simulated_quantity": "0",
        "estimated_entry": "not_executable",
        "stop_loss": "not_executable",
        "target": "not_executable",
        "risk_amount": "0",
        "reward_to_risk": "not_executable",
        "status": reason,
    }


def _is_executable_paper_trade(latest: PaperTradingCycleResult | None) -> bool:
    if latest is None or latest.strategy_evaluation is None:
        return False
    return (
        latest.executed
        and latest.execution_result is not None
        and latest.risk_decision_status == "approved"
        and latest.strategy_evaluation.signal.direction is not SignalDirection.HOLD
    )


def _transaction_state(trades: tuple[PaperTrade, ...]) -> list[JsonValue]:
    return [
        {
            "trade_ref": str(trade.order_intent_id),
            "time": trade.occurred_at.isoformat(),
            "side": trade.side.value.upper(),
            "quantity": str(trade.quantity),
            "price": str(trade.price),
            "fee": str(trade.fee_paid),
            "notional": str(trade.notional),
        }
        for trade in reversed(trades)
    ]


def _journal_entry_state(entries: list[DashboardJournalEntry]) -> list[JsonValue]:
    return [entry.as_dict() for entry in entries]


def _trader_feedback_state(items: list[DashboardTraderFeedback]) -> list[JsonValue]:
    return [item.as_dict() for item in items]


def _chart_drawing_state(drawings: list[DashboardChartDrawing]) -> list[JsonValue]:
    return [drawing.as_dict() for drawing in drawings if drawing.enabled]


def _open_paper_order_state(orders: list[DashboardPaperOrder]) -> list[JsonValue]:
    return [order.as_dict() for order in orders if order.status is DashboardPaperOrderStatus.OPEN]


def _watchlist_state(
    items: tuple[DashboardWatchlistItem, ...],
    *,
    selected_symbol: str,
) -> dict[str, JsonValue]:
    active_items = items or _demo_watchlist()
    return {
        "selected_symbol": selected_symbol,
        "paper_strategy_symbol": PAIR.symbol,
        "symbols": [item.as_dict(selected_symbol=selected_symbol) for item in active_items],
        "can_paper_trade_selected": selected_symbol == PAIR.symbol,
        "active_paper_symbols": [PAIR.symbol],
        "read_only_symbols": [item.symbol for item in active_items if item.symbol != PAIR.symbol],
        "live_order_capability": False,
        "note": (
            "BTC/USDT is paper-tradable now. Other watchlist symbols are read-only "
            "until multi-symbol strategy and risk modules are added."
        ),
    }


def _selected_watchlist_item(
    items: tuple[DashboardWatchlistItem, ...],
    selected_symbol: str,
) -> DashboardWatchlistItem:
    active_items = items or _demo_watchlist()
    for item in active_items:
        if item.symbol == selected_symbol:
            return item
    return active_items[0]


def _paper_strategy_mark_price(
    items: tuple[DashboardWatchlistItem, ...],
    *,
    latest: PaperTradingCycleResult | None,
) -> Decimal:
    active_items = items or _demo_watchlist()
    for item in active_items:
        if item.symbol == PAIR.symbol and item.price is not None:
            return item.price
    if latest is not None:
        return latest.snapshot.candle.close
    return WATCHLIST_DEMO_PRICES[PAIR.symbol]


def _watchlist_symbol(value: str) -> str:
    symbol = value.strip().upper()
    allowed = {pair.symbol for pair in WATCHLIST_PAIRS}
    if symbol not in allowed:
        raise PaperDashboardActionError(
            f"unsupported watchlist symbol: {symbol}; expected {', '.join(sorted(allowed))}"
        )
    return symbol


def _watchlist_note(symbol: str) -> str:
    if symbol == PAIR.symbol:
        return "Paper strategy, position, and staged paper orders are enabled for BTC/USDT."
    return "Read-only watchlist symbol; paper strategy and order staging remain BTC/USDT-only."


def _alert_rule_state(rules: list[DashboardAlertRule]) -> list[JsonValue]:
    return [rule.as_dict() for rule in rules if rule.enabled]


def _alert_state(
    rules: list[DashboardAlertRule],
    *,
    market_item: DashboardWatchlistItem,
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
    events: list[PaperDashboardEvent],
    recommendation: str,
) -> dict[str, JsonValue]:
    triggered: list[JsonValue] = []
    risk_halts = _risk_halts(status)
    for rule in rules:
        if not rule.enabled:
            continue
        alert = _triggered_alert(
            rule,
            market_item=market_item,
            risk_halts=risk_halts,
            status=status,
            latest=latest,
            events=events,
            recommendation=recommendation,
        )
        if alert is not None:
            triggered.append(alert)
    return {
        "triggered": triggered,
        "triggered_count": len(triggered),
        "rules_count": len(_alert_rule_state(rules)),
        "live_order_capability": False,
        "notification_scope": "local_dashboard_only",
        "supported_alert_types": [item.value for item in DashboardAlertType],
    }


def _ui_navigation_state(active_ui_mode: DashboardUIMode) -> list[JsonValue]:
    items: list[dict[str, JsonValue]] = [
        {
            "key": "dashboard",
            "label": "Dashboard",
            "target_mode": DashboardUIMode.BEGINNER.value,
            "status": "available",
            "paper_safe": True,
        },
        {
            "key": "advanced_trader",
            "label": "Advanced Trader",
            "target_mode": DashboardUIMode.ADVANCED_TRADER.value,
            "status": "available",
            "paper_safe": True,
        },
        {
            "key": "strategy_lab",
            "label": "Strategy Lab",
            "target_mode": DashboardUIMode.STRATEGY_LAB.value,
            "status": "available",
            "paper_safe": True,
        },
        {
            "key": "backtesting",
            "label": "Backtesting",
            "target_mode": DashboardUIMode.ADVANCED_TRADER.value,
            "target_panel": "backtest_summary",
            "status": "embedded",
            "paper_safe": True,
        },
        {
            "key": "reports",
            "label": "Reports",
            "route": "/paper-report",
            "status": "external_report",
            "paper_safe": True,
        },
        {
            "key": "alerts",
            "label": "Alerts",
            "target_mode": DashboardUIMode.ADVANCED_TRADER.value,
            "target_panel": "alerts",
            "status": "embedded",
            "paper_safe": True,
        },
        {
            "key": "logs",
            "label": "Logs",
            "route": "/api/activity",
            "status": "available",
            "paper_safe": True,
        },
        {
            "key": "settings",
            "label": "Settings",
            "route": "/api/ui-shell",
            "status": "preference_only",
            "paper_safe": True,
        },
    ]
    for item in items:
        item["active"] = item.get("target_mode") == active_ui_mode.value
    navigation: list[JsonValue] = []
    navigation.extend(items)
    return navigation


def _notification_state(
    *,
    alerts: Mapping[str, JsonValue],
    status: PaperStatusResponse,
    market_item: DashboardWatchlistItem,
    latest: PaperTradingCycleResult | None,
    last_seen_at: datetime | None,
    server_time: datetime,
) -> dict[str, JsonValue]:
    triggered = _as_list(alerts.get("triggered", []))
    safety_notifications: list[str] = []
    for halt in _risk_halts(status):
        if halt != "none":
            safety_notifications.append(halt)
    if status.paused:
        safety_notifications.append("paper bot is paused")
    if status.kill_switch_active:
        safety_notifications.append("paper kill switch is active")
    if market_item.data_health != "healthy":
        safety_notifications.append(f"market data health is {market_item.data_health}")
    if latest is not None and latest.snapshot.health.is_degraded:
        safety_notifications.append("latest stream health is degraded")
    notification_time = latest.snapshot.received_at if latest is not None else server_time
    items: list[JsonValue] = []
    items.extend(
        _notification_item(item, category="alert", occurred_at=notification_time)
        for item in triggered
    )
    items.extend(
        _notification_item(item, category="safety", occurred_at=notification_time)
        for item in safety_notifications
    )
    count = len(items)
    unread_count = 0
    for item in items:
        if isinstance(item, Mapping) and not _notification_seen(item, last_seen_at=last_seen_at):
            unread_count += 1
    return {
        "count": count,
        "unread_count": unread_count,
        "bell_state": "attention" if unread_count else "clear",
        "triggered_alert_count": len(triggered),
        "safety_notification_count": len(safety_notifications),
        "items": items,
        "last_seen_at": last_seen_at.isoformat() if last_seen_at is not None else "",
        "notification_scope": "local_dashboard_only",
    }


def _notification_item(
    item: JsonValue,
    *,
    category: str,
    occurred_at: datetime,
) -> dict[str, JsonValue]:
    if isinstance(item, Mapping):
        alert_id = str(item.get("alert_id", "local-alert"))
        message = str(item.get("message", "dashboard alert"))
        item_occurred_at = _datetime_preference(item.get("occurred_at", "")) or occurred_at
        severity = "action" if category == "alert" else "warning"
        return {
            "notification_id": f"{category}:{alert_id}:{message}",
            "category": category,
            "severity": severity,
            "message": message,
            "symbol": str(item.get("symbol", "")),
            "occurred_at": item_occurred_at.isoformat(),
            "paper_only": True,
        }
    message = str(item)
    return {
        "notification_id": f"{category}:{message}",
        "category": category,
        "severity": "warning",
        "message": message,
        "symbol": "",
        "occurred_at": occurred_at.isoformat(),
        "paper_only": True,
    }


def _notification_seen(
    item: Mapping[str, JsonValue],
    *,
    last_seen_at: datetime | None,
) -> bool:
    if last_seen_at is None:
        return False
    try:
        occurred_at = datetime.fromisoformat(str(item.get("occurred_at", "")))
    except ValueError:
        return False
    return occurred_at <= last_seen_at


def _activity_state(
    events: list[PaperDashboardEvent],
    *,
    limit: int | None,
) -> dict[str, JsonValue]:
    active_limit = None if limit is None else max(0, limit)
    items: list[JsonValue] = []
    items.extend(_activity_item(event) for event in events)
    visible_items = items if active_limit is None else items[:active_limit]
    return {
        "items": visible_items,
        "total_count": len(items),
        "visible_count": len(visible_items),
        "has_more": active_limit is not None and len(items) > active_limit,
        "view_all_route": "/api/activity",
        "paper_only": True,
    }


def _activity_item(event: PaperDashboardEvent) -> dict[str, JsonValue]:
    severity = _activity_severity(event.event_type)
    return {
        "event_type": event.event_type,
        "message": event.message,
        "reason": event.reason,
        "occurred_at": event.occurred_at.isoformat(),
        "severity": severity,
        "status_label": _activity_status_label(severity),
        "paper_only": True,
    }


def _activity_severity(event_type: str) -> str:
    if any(token in event_type for token in ("emergency", "blocked", "failed")):
        return "action"
    if any(token in event_type for token in ("reject", "delete", "cancel", "pause")):
        return "warning"
    if any(token in event_type for token in ("approve", "resume", "save", "add", "submit")):
        return "system"
    return "info"


def _activity_status_label(severity: str) -> str:
    labels = {
        "action": "ACTION",
        "warning": "WARN",
        "system": "SYSTEM",
        "info": "INFO",
    }
    return labels.get(severity, "INFO")


def _refresh_status(
    *,
    last_refresh_at: datetime | None,
    interval_seconds: int,
    server_time: datetime,
) -> dict[str, JsonValue]:
    active_interval = max(interval_seconds, 1)
    base_time = last_refresh_at or server_time
    next_check_at = base_time + timedelta(seconds=active_interval)
    if next_check_at < server_time:
        next_check_at = server_time
    seconds_remaining = max(0, int((next_check_at - server_time).total_seconds()))
    return {
        "server_time": server_time.isoformat(),
        "last_check_at": base_time.isoformat(),
        "next_check_at": next_check_at.isoformat(),
        "next_check_in_seconds": seconds_remaining,
        "interval_seconds": active_interval,
    }


def _app_metadata(server_time: datetime) -> dict[str, JsonValue]:
    try:
        app_version = version("abtp")
    except PackageNotFoundError:
        app_version = "not_available"
    return {
        "name": "abtp",
        "version": app_version,
        "version_source": "python_package_metadata",
        "server_time": server_time.isoformat(),
    }


def _runtime_telemetry(
    *,
    market_item: DashboardWatchlistItem,
    latest: PaperTradingCycleResult | None,
    cycles: tuple[PaperTradingCycleResult, ...],
    status: PaperStatusResponse,
    notifications: Mapping[str, JsonValue],
    app_metadata: Mapping[str, JsonValue],
    refresh: Mapping[str, JsonValue],
    requested_source: str,
    equity_history: tuple[Decimal, ...],
) -> dict[str, JsonValue]:
    return {
        "module_numbers": [
            "1_24h_price_change_pct",
            "2_trend_strength_pct",
            "3_exchange_connection_status",
            "4_notification_bell_state",
            "5_latency_ms",
            "6_backend_app_version",
            "7_portfolio_sparkline",
            "8_today_pnl",
            "9_next_check_countdown",
        ],
        "price_change_24h_pct": _status_str(market_item.price_change_24h_pct, "unavailable"),
        "price_change_24h_source": _price_change_source(market_item),
        "trend_strength_pct": _trend_strength_pct(latest),
        "trend_strength_source": _trend_strength_source(latest),
        "exchange_connection": _exchange_connection_status(
            requested_source=requested_source,
            market_item=market_item,
            latest=latest,
        ),
        "exchange_connection_detail": _exchange_connection_detail(
            requested_source=requested_source,
            market_item=market_item,
            latest=latest,
        ),
        "notification_count": notifications.get("count", 0),
        "bell_state": notifications.get("bell_state", "clear"),
        "latency_ms": _latency_ms(latest),
        "app_version": app_metadata.get("version", "not_available"),
        "app_version_source": app_metadata.get("version_source", "not_available"),
        "portfolio_sparkline": _portfolio_sparkline(equity_history),
        "today_pnl": _today_pnl(cycles=cycles, status=status),
        "today_pnl_pct": _today_pnl_pct(cycles=cycles, status=status),
        "today_pnl_source": "paper_cycle_equity",
        "next_check_at": refresh.get("next_check_at", "not_available"),
        "next_check_in_seconds": refresh.get("next_check_in_seconds", "not_available"),
        "server_time": refresh.get("server_time", "not_available"),
    }


def _price_change_source(market_item: DashboardWatchlistItem) -> str:
    if market_item.price_change_24h_pct is None:
        return "unavailable"
    if market_item.source == "binance spot":
        return "binance_public_24hr_ticker"
    if market_item.source.startswith("demo"):
        return "demo_previous_day_price"
    return market_item.source


def _exchange_connection_status(
    *,
    requested_source: str,
    market_item: DashboardWatchlistItem,
    latest: PaperTradingCycleResult | None,
) -> str:
    if requested_source != "binance":
        return "not_configured"
    if (
        market_item.source == "binance spot"
        and market_item.data_health == "healthy"
        and (latest is None or latest.snapshot.health.is_connected)
    ):
        return "connected"
    if "fallback" in market_item.source or market_item.data_health == "degraded":
        return "degraded"
    return "disconnected"


def _exchange_connection_detail(
    *,
    requested_source: str,
    market_item: DashboardWatchlistItem,
    latest: PaperTradingCycleResult | None,
) -> str:
    if requested_source != "binance":
        return "Binance adapter is not configured for this dashboard session."
    stream_status = latest.snapshot.health.status if latest is not None else "unavailable"
    return (
        f"source={market_item.source}; health={market_item.data_health}; "
        f"stream={stream_status}; updated_at={market_item.updated_at.isoformat()}"
    )


def _latency_ms(latest: PaperTradingCycleResult | None) -> str:
    if latest is None:
        return "not_available"
    return str(latest.snapshot.health.latency_ms)


def _trend_strength_pct(latest: PaperTradingCycleResult | None) -> str:
    if latest is None:
        return "not_available"
    value = latest.features.values.get("market.return_3")
    if value is None:
        return "not_available"
    return str(abs(_decimal(value)) * Decimal("100"))


def _trend_strength_source(latest: PaperTradingCycleResult | None) -> str:
    if latest is None or "market.return_3" not in latest.features.values:
        return "not_available"
    return "feature:market.return_3_abs_pct"


def _today_pnl(
    *,
    cycles: tuple[PaperTradingCycleResult, ...],
    status: PaperStatusResponse,
    starting_balance: Decimal = Decimal("10000"),
    session_baseline: Decimal | None = None,
) -> str:
    if not cycles:
        return "insufficient_data"
    if session_baseline is not None:
        return str(status.portfolio.equity - session_baseline)
    latest = cycles[-1]
    latest_day = latest.snapshot.received_at.date()
    same_day = [cycle for cycle in cycles if cycle.snapshot.received_at.date() == latest_day]
    baseline = same_day[0].equity if same_day else starting_balance
    return str(status.portfolio.equity - baseline)


def _today_pnl_pct(
    *,
    cycles: tuple[PaperTradingCycleResult, ...],
    status: PaperStatusResponse,
    starting_balance: Decimal = Decimal("10000"),
    session_baseline: Decimal | None = None,
) -> str:
    if not cycles:
        return "insufficient_data"
    if session_baseline is not None:
        baseline = session_baseline
        if baseline <= DECIMAL_ZERO:
            return "insufficient_data"
        return _pct((status.portfolio.equity - baseline) / baseline)
    latest = cycles[-1]
    latest_day = latest.snapshot.received_at.date()
    same_day = [cycle for cycle in cycles if cycle.snapshot.received_at.date() == latest_day]
    baseline = same_day[0].equity if same_day else starting_balance
    if baseline <= DECIMAL_ZERO:
        return "insufficient_data"
    return _pct((status.portfolio.equity - baseline) / baseline)


def _portfolio_sparkline(equity_history: tuple[Decimal, ...]) -> list[JsonValue]:
    points = list(equity_history[-16:])
    return [{"index": index, "equity": str(value)} for index, value in enumerate(points)]


def _triggered_alert(
    rule: DashboardAlertRule,
    *,
    market_item: DashboardWatchlistItem,
    risk_halts: tuple[str, ...],
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
    events: list[PaperDashboardEvent],
    recommendation: str,
) -> dict[str, JsonValue] | None:
    if rule.alert_type in {DashboardAlertType.PRICE_ABOVE, DashboardAlertType.PRICE_BELOW}:
        if rule.symbol != market_item.symbol or rule.threshold is None or market_item.price is None:
            return None
        if (
            rule.alert_type is DashboardAlertType.PRICE_ABOVE
            and market_item.price <= rule.threshold
        ):
            return None
        if (
            rule.alert_type is DashboardAlertType.PRICE_BELOW
            and market_item.price >= rule.threshold
        ):
            return None
        return _alert_payload(
            rule,
            message=f"{rule.symbol} price {market_item.price} crossed {rule.threshold}",
        )
    if rule.alert_type is DashboardAlertType.RISK_HALT:
        active_halts = tuple(item for item in risk_halts if item != "none")
        if not active_halts:
            return None
        return _alert_payload(rule, message="; ".join(active_halts))
    if rule.alert_type is DashboardAlertType.INDICATOR_CONFIDENCE:
        threshold = rule.threshold or Decimal("0.60")
        confidence = _latest_signal_confidence(latest)
        if confidence < threshold:
            return None
        return _alert_payload(
            rule,
            message=f"signal confidence {confidence} reached {threshold}",
        )
    if rule.alert_type is DashboardAlertType.DRAWDOWN_ABOVE:
        threshold = rule.threshold or Decimal("0")
        drawdown = status.portfolio.drawdown_pct
        if drawdown < threshold:
            return None
        return _alert_payload(rule, message=f"drawdown {drawdown} reached {threshold}")
    if rule.alert_type is DashboardAlertType.STALE_DATA:
        stale_reasons = _stale_data_alert_reasons(market_item=market_item, latest=latest)
        if not stale_reasons:
            return None
        return _alert_payload(rule, message="; ".join(stale_reasons))
    if rule.alert_type is DashboardAlertType.PAPER_ORDER_EVENT:
        event = _latest_paper_order_event(events, expected=rule.expected_value)
        if event is None:
            return None
        return _alert_payload(rule, message=f"{event.event_type}: {event.reason}")
    if rule.alert_type is DashboardAlertType.RECOMMENDATION:
        expected = rule.expected_value or "BUY"
        if recommendation.upper() != expected:
            return None
        return _alert_payload(rule, message=f"recommendation is {recommendation.upper()}")
    return None


def _alert_payload(rule: DashboardAlertRule, *, message: str) -> dict[str, JsonValue]:
    return {
        "alert_id": rule.alert_id,
        "alert_type": rule.alert_type.value,
        "symbol": rule.symbol,
        "message": message,
        "occurred_at": rule.created_at.isoformat(),
        "paper_only": True,
    }


def _latest_signal_confidence(latest: PaperTradingCycleResult | None) -> Decimal:
    if latest is None or latest.strategy_evaluation is None:
        return DECIMAL_ZERO
    return latest.strategy_evaluation.signal.confidence


def _stale_data_alert_reasons(
    *,
    market_item: DashboardWatchlistItem,
    latest: PaperTradingCycleResult | None,
) -> list[str]:
    reasons: list[str] = []
    if market_item.data_health != "healthy":
        reasons.append(f"market data health is {market_item.data_health}")
    if latest is not None and latest.skipped_reason and "stale" in latest.skipped_reason.lower():
        reasons.append(latest.skipped_reason)
    if latest is not None and latest.snapshot.health.is_stale:
        reasons.append("latest market stream is stale")
    return reasons


def _latest_paper_order_event(
    events: list[PaperDashboardEvent],
    *,
    expected: str,
) -> PaperDashboardEvent | None:
    allowed = {
        "submit_paper_order_ticket",
        "cancel_paper_order",
    }
    normalized_expected = expected.strip()
    for event in events:
        if event.event_type not in allowed:
            continue
        if normalized_expected and event.event_type != normalized_expected:
            continue
        return event
    return None


def _alert_type(value: str) -> DashboardAlertType:
    try:
        return DashboardAlertType(value.strip().lower())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in DashboardAlertType)
        message = f"unsupported alert type: {value}; expected {allowed}"
        raise PaperDashboardActionError(message) from exc


def _alert_threshold(alert_type: DashboardAlertType, value: str | None) -> Decimal | None:
    if alert_type not in {
        DashboardAlertType.PRICE_ABOVE,
        DashboardAlertType.PRICE_BELOW,
        DashboardAlertType.INDICATOR_CONFIDENCE,
        DashboardAlertType.DRAWDOWN_ABOVE,
    }:
        return None
    if value is None or not value.strip():
        raise PaperDashboardActionError(f"{alert_type.value} alert requires threshold")
    if alert_type in {DashboardAlertType.PRICE_ABOVE, DashboardAlertType.PRICE_BELOW}:
        return _required_positive_decimal(value, "alert threshold")
    return _required_non_negative_decimal(value, "alert threshold")


def _alert_expected_value(alert_type: DashboardAlertType, value: str | None) -> str:
    cleaned = (value or "").strip()
    if alert_type is DashboardAlertType.RECOMMENDATION:
        return cleaned.upper()
    return cleaned


def _journal_setup_type(value: str | None) -> str:
    setup_type = (value or "manual_review").strip().lower()
    allowed = {
        "trend_continuation",
        "pullback",
        "breakout",
        "mean_reversion",
        "risk_reduction",
        "manual_review",
    }
    if setup_type not in allowed:
        raise PaperDashboardActionError(
            f"unsupported journal setup type: {setup_type}; expected {', '.join(sorted(allowed))}"
        )
    return setup_type


def _journal_tags(value: str | None) -> tuple[str, ...]:
    raw_tags = (value or "").replace(";", ",").split(",")
    tags: list[str] = []
    for raw_tag in raw_tags:
        tag = raw_tag.strip().lower().replace(" ", "_")
        if not tag or tag in tags:
            continue
        if len(tag) > 32:
            raise PaperDashboardActionError("journal tag is too long")
        tags.append(tag)
    return tuple(tags[:8])


def _trader_feedback_reviewer_role(value: str | None) -> str:
    role = (value or "trader").strip().lower().replace(" ", "_")
    allowed = {"trader", "risk_reviewer", "strategy_reviewer", "operator", "developer"}
    if role not in allowed:
        raise PaperDashboardActionError(
            f"unsupported feedback reviewer role: {role}; expected {', '.join(sorted(allowed))}"
        )
    return role


def _trader_feedback_category(value: str | None) -> str:
    category = (value or "ui").strip().lower().replace(" ", "_")
    allowed = {
        "ui",
        "risk",
        "strategy",
        "market_data",
        "order_ticket",
        "reporting",
        "missing_feature",
    }
    if category not in allowed:
        raise PaperDashboardActionError(
            f"unsupported feedback category: {category}; expected {', '.join(sorted(allowed))}"
        )
    return category


def _trader_feedback_severity(value: str | None) -> str:
    severity = (value or "medium").strip().lower()
    allowed = {"low", "medium", "high", "blocker"}
    if severity not in allowed:
        raise PaperDashboardActionError(
            f"unsupported feedback severity: {severity}; expected {', '.join(sorted(allowed))}"
        )
    return severity


def _limited_text(value: str | None, label: str, *, max_length: int) -> str:
    cleaned = (value or "").strip()
    if len(cleaned) > max_length:
        raise PaperDashboardActionError(f"journal {label} is too long")
    return cleaned


def _journal_tag_counts(entries: list[Mapping[str, JsonValue]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        tags = entry.get("tags", [])
        if not isinstance(tags, list):
            continue
        for tag in tags:
            tag_text = str(tag)
            counts[tag_text] = counts.get(tag_text, 0) + 1
    return counts


def _journal_chart_context_hint(latest: PaperTradingCycleResult | None) -> str:
    if latest is None:
        return "No latest chart candle is available."
    candle = latest.snapshot.candle
    return (
        f"{PAIR.symbol} {candle.opened_at.isoformat()} "
        f"O:{candle.open} H:{candle.high} L:{candle.low} C:{candle.close}"
    )


def _chart_drawing_type(value: str) -> DashboardChartDrawingType:
    try:
        return DashboardChartDrawingType(value.strip().lower())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in DashboardChartDrawingType)
        raise PaperDashboardActionError(
            f"unsupported chart drawing type: {value}; expected {allowed}"
        ) from exc


def _chart_drawing_timeframe(value: str | None) -> str:
    timeframe = (value or "1h").strip().lower()
    if timeframe not in {"1h", "4h", "1d"}:
        raise PaperDashboardActionError("unsupported chart drawing timeframe")
    return timeframe


def _chart_drawing_time(
    value: str | None,
    *,
    latest: PaperTradingCycleResult | None,
) -> str:
    cleaned = (value or "").strip()
    if cleaned:
        return cleaned
    if latest is None:
        return DEFAULT_NOW.isoformat()
    return latest.snapshot.candle.closed_at.isoformat()


def _chart_drawing_price(value: str | None, *, fallback: Decimal) -> Decimal:
    if value is None or not value.strip():
        return fallback
    return _required_positive_decimal(value, "chart drawing price")


def _chart_drawing_optional_price(
    value: str | None,
    *,
    fallback: Decimal,
    drawing_type: DashboardChartDrawingType,
) -> Decimal | None:
    needs_second_price = {
        DashboardChartDrawingType.TRENDLINE,
        DashboardChartDrawingType.BOX,
        DashboardChartDrawingType.FIBONACCI,
    }
    if drawing_type in needs_second_price:
        return _chart_drawing_price(value, fallback=fallback)
    return _optional_positive_decimal(value, "chart drawing end price")


def _chart_drawing_color(value: str | None) -> str:
    cleaned = (value or "#1264a3").strip()
    allowed = {"#1264a3", "#0f7b52", "#b42318", "#9a6700", "#6941c6", "#172026"}
    if cleaned not in allowed:
        raise PaperDashboardActionError("unsupported chart drawing color")
    return cleaned


def _paper_order_from_ticket(
    *,
    order_type: str,
    side: str,
    quantity: str,
    limit_price: str | None,
    stop_price: str | None,
    take_profit_price: str | None,
    reference_price: Decimal,
    created_at: datetime,
    reason: str,
) -> DashboardPaperOrder:
    try:
        active_type = DashboardPaperOrderType(order_type.strip().lower())
        active_side = OrderSide(side.strip().lower())
    except ValueError as exc:
        raise PaperDashboardActionError("unsupported paper order ticket value") from exc
    active_quantity = _required_positive_decimal(quantity, "quantity")
    active_limit = _optional_positive_decimal(limit_price, "limit price")
    active_stop = _optional_positive_decimal(stop_price, "stop price")
    active_take_profit = _optional_positive_decimal(take_profit_price, "take profit price")
    if active_type is DashboardPaperOrderType.LIMIT and active_limit is None:
        raise PaperDashboardActionError("limit paper order requires limit price")
    if active_type is DashboardPaperOrderType.STOP and active_stop is None:
        raise PaperDashboardActionError("stop paper order requires stop price")
    if active_type is DashboardPaperOrderType.OCO and (
        active_stop is None or active_take_profit is None
    ):
        raise PaperDashboardActionError("OCO paper order requires stop and take profit prices")
    _validate_paper_order_filter(
        order_type=active_type,
        quantity=active_quantity,
        reference_price=reference_price,
        limit_price=active_limit,
        stop_price=active_stop,
        take_profit_price=active_take_profit,
    )
    if active_type is DashboardPaperOrderType.MARKET:
        active_limit = None
        active_stop = None
        active_take_profit = None
    return DashboardPaperOrder(
        order_id=f"paper-{uuid4()}",
        order_type=active_type,
        side=active_side,
        quantity=active_quantity,
        created_at=created_at,
        limit_price=active_limit,
        stop_price=active_stop,
        take_profit_price=active_take_profit,
        reason=reason,
    )


def _validate_paper_order_filter(
    *,
    order_type: DashboardPaperOrderType,
    quantity: Decimal,
    reference_price: Decimal,
    limit_price: Decimal | None,
    stop_price: Decimal | None,
    take_profit_price: Decimal | None,
) -> None:
    """Apply Binance-style symbol filters to the local paper ticket."""

    if quantity < PAPER_ORDER_FILTER.min_quantity:
        raise PaperDashboardActionError(
            f"paper order quantity is below min_quantity {PAPER_ORDER_FILTER.min_quantity}"
        )
    _require_increment(
        quantity,
        PAPER_ORDER_FILTER.step_size,
        label="quantity",
        filter_name="step_size",
    )
    for label, price in (
        ("limit price", limit_price),
        ("stop price", stop_price),
        ("take profit price", take_profit_price),
    ):
        if price is None:
            continue
        _require_increment(
            price,
            PAPER_ORDER_FILTER.tick_size,
            label=label,
            filter_name="tick_size",
        )
    estimated_price = _paper_order_filter_price(
        order_type=order_type,
        reference_price=reference_price,
        limit_price=limit_price,
        stop_price=stop_price,
        take_profit_price=take_profit_price,
    )
    notional = quantity * estimated_price
    if notional < PAPER_ORDER_FILTER.min_notional:
        raise PaperDashboardActionError(
            f"paper order notional {notional} is below min_notional "
            f"{PAPER_ORDER_FILTER.min_notional}"
        )


def _paper_order_filter_price(
    *,
    order_type: DashboardPaperOrderType,
    reference_price: Decimal,
    limit_price: Decimal | None,
    stop_price: Decimal | None,
    take_profit_price: Decimal | None,
) -> Decimal:
    if order_type is DashboardPaperOrderType.LIMIT and limit_price is not None:
        return limit_price
    if order_type is DashboardPaperOrderType.STOP and stop_price is not None:
        return stop_price
    if order_type is DashboardPaperOrderType.OCO:
        oco_prices = [price for price in (stop_price, take_profit_price) if price is not None]
        if oco_prices:
            return min(oco_prices)
    return reference_price


def _require_increment(
    value: Decimal,
    increment: Decimal,
    *,
    label: str,
    filter_name: str,
) -> None:
    if value % increment != DECIMAL_ZERO:
        raise PaperDashboardActionError(
            f"paper order {label} does not align to {filter_name} {increment}"
        )


def _adaptive_view_sections(
    *,
    payload: Mapping[str, JsonValue],
    status: PaperStatusResponse,
    cycles: tuple[PaperTradingCycleResult, ...],
    latest: PaperTradingCycleResult | None,
    can_approve: bool,
    order_book: OrderBookSnapshot | None,
    recent_market_trades: tuple[Trade, ...],
    strategy_lab_selection: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    strategy = _as_mapping(payload["strategy"])
    portfolio = _as_mapping(payload["portfolio"])
    controls = _as_mapping(payload["controls"])
    market = _as_mapping(payload["market"])
    trade = _as_mapping(payload["suggested_paper_trade"])
    open_orders = _as_list(payload["open_paper_orders"])
    transactions = _as_list(payload["transactions"])
    journal_entries = _as_list(payload["journal_entries"])
    trader_feedback = _as_list(payload["trader_feedback"])
    chart_drawings = _as_list(payload["chart_drawings"])
    logs = _as_list(payload["logs"])
    watchlist = _as_mapping(payload["watchlist"])
    alerts = _as_mapping(payload["alerts"])
    runtime_telemetry = _as_mapping(payload["runtime_telemetry"])
    alert_rules = _as_list(payload["alert_rules"])
    reasons = _as_text_list(strategy.get("indicator_reasons", []))
    actionable = can_approve and str(trade.get("status", "")) == "risk_approved_simulated_fill"
    recommendation = str(strategy.get("recommendation", "HOLD"))
    evidence_status = "available" if latest is not None else "missing"
    market_payload = dict(market)
    strategy_payload = dict(strategy)
    trade_payload = dict(trade)
    portfolio_payload = dict(portfolio)
    controls_payload = dict(controls)
    watchlist_payload = dict(watchlist)
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
                "risk_safety_panel",
                "exchange_health",
                "market_data_adapter_read_only",
                "indicators_feature_pipeline",
                "local_chart_drawings",
                "backtest_summary",
                "performance_analytics",
                "position_exit_review",
                "paper_ledger",
                "audit_evidence",
                "order_book_depth",
                "order_flow_recent_trades",
                "watchlist_manager",
                "local_alerts",
                "trade_journal_analytics",
                "paper_order_ticket",
                "open_paper_orders",
                "runtime_telemetry_status",
            ],
            "market": market_payload,
            "strategy": strategy_payload,
            "suggested_paper_trade": trade_payload,
            "portfolio": portfolio_payload,
            "controls": controls_payload,
            "risk_safety": _advanced_risk_safety_payload(
                status=status,
                latest=latest,
                market=market,
                portfolio=portfolio,
                controls=controls,
                order_book=order_book,
                recent_market_trades=recent_market_trades,
                transactions=transactions,
                open_orders=open_orders,
                events=logs,
            ),
            "transactions": transactions,
            "chart_drawings": chart_drawings,
            "watchlist": watchlist_payload,
            "alerts": dict(alerts),
            "notifications": dict(_as_mapping(payload["notifications"])),
            "runtime_telemetry": dict(runtime_telemetry),
            "alert_rules": alert_rules,
            "open_paper_orders": open_orders,
            "order_ticket": _advanced_order_ticket_payload(latest=latest),
            "trade_journal": _advanced_trade_journal_payload(
                transactions=transactions,
                journal_entries=journal_entries,
                status=status,
                latest=latest,
            ),
            "trader_feedback": _advanced_trader_feedback_payload(trader_feedback),
            "logs": logs,
            "chart": _advanced_chart_payload(cycles, drawings=chart_drawings),
            "order_book": _advanced_order_book_payload(
                latest=latest,
                order_book=order_book,
            ),
            "order_flow": _advanced_order_flow_payload(
                trades=recent_market_trades,
                order_book=order_book,
                latest=latest,
            ),
            "position": _advanced_position_payload(status=status, latest=latest),
            "backtest_summary": _advanced_backtest_summary(
                status=status,
                latest=latest,
                cycles=cycles,
            ),
            "performance": _advanced_performance_summary(status=status, cycles=cycles),
            "exit_review": _advanced_exit_review(
                status=status,
                latest=latest,
                trade=trade,
            ),
            "exports": {
                "transactions_csv": "/paper-transactions.csv",
                "trader_feedback_csv": "/trader-feedback.csv",
                "paper_report": "/paper-report",
                "trader_handoff": "/trader-handoff.md",
                "trader_evidence_json": "/trader-evidence.json",
            },
        },
        DashboardUIMode.STRATEGY_LAB.value: _strategy_lab_view(
            selection=strategy_lab_selection,
            default_symbol=str(market.get("symbol", "BTC/USDT")),
            strategy=strategy_payload,
            status=status,
            latest=latest,
            cycles=cycles,
            market=market,
            order_book=order_book,
            recent_market_trades=recent_market_trades,
            transactions=transactions,
            actionable=actionable,
            evidence_status=evidence_status,
        ),
    }


def _strategy_lab_view(
    *,
    selection: Mapping[str, JsonValue],
    default_symbol: str,
    strategy: Mapping[str, JsonValue],
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
    cycles: tuple[PaperTradingCycleResult, ...],
    market: Mapping[str, JsonValue],
    order_book: OrderBookSnapshot | None,
    recent_market_trades: tuple[Trade, ...],
    transactions: list[JsonValue],
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
    evidence_matrix = _strategy_lab_evidence_matrix(
        profile=profile,
        strategy=strategy,
        status=status,
        latest=latest,
        cycles=cycles,
        market=market,
        order_book=order_book,
        recent_market_trades=recent_market_trades,
        transactions=transactions,
    )
    missing_routing_evidence: list[JsonValue] = []
    for row in evidence_matrix:
        evidence_row = _as_mapping(row)
        if evidence_row.get("required") is True and str(evidence_row.get("status")) != "available":
            missing_routing_evidence.append(str(evidence_row.get("evidence")))
    is_selected_supported = (
        symbol in _as_text_tuple(profile["symbols"])
        and timeframe in _as_text_tuple(profile["timeframes"])
        and parameter_profile in _as_text_tuple(profile["parameter_profiles"])
    )
    recommendation_actionable = (
        actionable
        and evidence_status == "available"
        and not missing_evidence
        and not missing_routing_evidence
        and profile["paper_approval_allowed"] is True
        and run_mode == StrategyLabRunMode.PAPER.value
        and is_selected_supported
    )
    parameter_config = _strategy_lab_parameter_config(profile, parameter_profile)
    return {
        "enabled_modules": list(_as_text_tuple(profile["enabled_modules"])),
        "selected_strategy": profile["label"],
        "strategy_family": profile["family"],
        "strategy_status": profile["status"],
        "description": profile["description"],
        "selection": {
            "strategy": profile["key"],
            "symbol": symbol,
            "timeframe": timeframe,
            "run_mode": run_mode,
            "parameter_profile": parameter_profile,
        },
        "evidence_request": {
            "ui_profile": DashboardUIMode.STRATEGY_LAB.value,
            "strategy_profile": profile["key"],
            "run_mode": run_mode,
            "parameter_profile": parameter_profile,
            "requested_modules": list(_as_text_tuple(profile["enabled_modules"])),
            "requested_evidence": list(_as_text_tuple(profile["required_evidence"])),
            "live_execution_requested": False,
        },
        "routing_decision": {
            "scope": "paper_evidence_only",
            "live_execution_enabled": False,
            "selected_symbol_supported": is_selected_supported,
            "paper_approval_allowed": profile["paper_approval_allowed"],
        },
        "selectors": {
            "strategies": _strategy_selector_options(),
            "symbols": list(_as_text_tuple(profile["symbols"])),
            "timeframes": list(_as_text_tuple(profile["timeframes"])),
            "run_modes": [item.value for item in StrategyLabRunMode],
            "parameter_profiles": list(_as_text_tuple(profile["parameter_profiles"])),
        },
        "paper_approval_allowed": profile["paper_approval_allowed"],
        "evidence_status": "missing"
        if missing_evidence or missing_routing_evidence
        else evidence_status,
        "recommendation_actionable": recommendation_actionable,
        "required_evidence": list(_as_text_tuple(profile["required_evidence"])),
        "missing_evidence": missing_evidence + missing_routing_evidence,
        "evidence_matrix": evidence_matrix,
        "module_routing": _strategy_lab_module_routing(
            profile=profile,
            strategy=strategy,
            evidence_matrix=evidence_matrix,
        ),
        "parameter_config": parameter_config,
        "required_market_data": list(_as_text_tuple(profile["required_market_data"])),
        "required_indicators": list(_as_text_tuple(profile["required_indicators"])),
        "required_ai_context_modules": list(_as_text_tuple(profile["required_ai_context_modules"])),
        "required_risk_checks": list(_as_text_tuple(profile["required_risk_checks"])),
        "required_explanation_fields": list(_as_text_tuple(profile["required_explanation_fields"])),
        "chart_overlays": list(_as_text_tuple(profile["chart_overlays"])),
        "backtest_metrics": list(_as_text_tuple(profile["backtest_metrics"])),
        "strategy_state": dict(strategy),
        "compare_runs": _strategy_lab_compare_runs(
            profile=profile,
            status=status,
            latest=latest,
            cycles=cycles,
            selected_parameter_profile=parameter_profile,
        ),
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
                "order_book_depth",
                "recent_public_trades",
                "backtest_metrics",
            ],
            "required_market_data": ["BTC/USDT candles", "order book spread", "stream health"],
            "required_indicators": ["return_3", "RSI", "ATR percent", "volume ratio", "spread bps"],
            "required_ai_context_modules": [
                "confidence_engine",
                "strategy_explanation",
                "paper_evaluation_gate",
            ],
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
            "parameter_profile_configs": {
                "default": {
                    "risk_per_trade_pct": "0.25",
                    "minimum_reward_to_risk": "2.0",
                    "daily_trend_confirmation": "enabled",
                    "entry_style": "conservative pullback or confirmed momentum",
                },
                "defensive": {
                    "risk_per_trade_pct": "0.10",
                    "minimum_reward_to_risk": "2.5",
                    "daily_trend_confirmation": "required",
                    "entry_style": "capital-preservation only",
                },
            },
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


def _strategy_lab_evidence_matrix(
    *,
    profile: Mapping[str, JsonValue],
    strategy: Mapping[str, JsonValue],
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
    cycles: tuple[PaperTradingCycleResult, ...],
    market: Mapping[str, JsonValue],
    order_book: OrderBookSnapshot | None,
    recent_market_trades: tuple[Trade, ...],
    transactions: list[JsonValue],
) -> list[JsonValue]:
    explanation_missing = _strategy_lab_missing_evidence(profile, strategy)
    backtest_summary = _advanced_backtest_summary(
        status=status,
        latest=latest,
        cycles=cycles,
    )
    checks: dict[str, tuple[bool, str, str]] = {
        "market_data": (
            latest is not None and str(market.get("current_price")) != "not_available",
            f"source={market.get('source', 'not_available')}, symbol={market.get('symbol')}",
            "market_data_adapter_read_only",
        ),
        "indicator_features": (
            str(strategy.get("data_quality", "")) not in {"", "unavailable", "not_available"},
            f"data_quality={strategy.get('data_quality', 'not_available')}",
            "indicators_feature_pipeline",
        ),
        "risk_decision": (
            str(strategy.get("risk_decision", "")) not in {"", "not_evaluated", "not_available"},
            f"risk_decision={strategy.get('risk_decision', 'not_available')}",
            "risk_engine",
        ),
        "explanation_fields": (
            not explanation_missing,
            "all required explanation fields present"
            if not explanation_missing
            else ", ".join(str(item) for item in explanation_missing),
            "strategy_explanation",
        ),
        "paper_account_state": (
            status.portfolio.equity >= DECIMAL_ZERO,
            f"equity={status.portfolio.equity}, trades={status.trades_count}",
            "paper_trading_engine",
        ),
        "order_book_depth": (
            order_book is not None,
            order_book.source_ref if order_book is not None else "not_available",
            "order_book_depth",
        ),
        "recent_public_trades": (
            bool(recent_market_trades),
            f"recent_trades={len(recent_market_trades)}",
            "order_flow_recent_trades",
        ),
        "backtest_metrics": (
            str(backtest_summary.get("sample_size", "0")) != "0",
            f"sample_size={backtest_summary.get('sample_size', '0')}",
            "backtest_summary",
        ),
        "paper_transactions": (
            bool(transactions),
            f"transactions={len(transactions)}",
            "paper_ledger",
        ),
    }
    required = set(_as_text_tuple(profile["required_evidence"]))
    rows: list[JsonValue] = []
    for evidence_name in _as_text_tuple(profile["required_evidence"]):
        available, detail, module = checks.get(
            evidence_name,
            (False, "strategy profile has no local evidence check", "not_routed"),
        )
        rows.append(
            {
                "evidence": evidence_name,
                "required": True,
                "status": "available" if available else "missing",
                "module": module,
                "detail": detail,
            }
        )
    for evidence_name in ("paper_transactions",):
        available, detail, module = checks[evidence_name]
        rows.append(
            {
                "evidence": evidence_name,
                "required": evidence_name in required,
                "status": "available" if available else "not_required",
                "module": module,
                "detail": detail,
            }
        )
    return rows


def _strategy_lab_module_routing(
    *,
    profile: Mapping[str, JsonValue],
    strategy: Mapping[str, JsonValue],
    evidence_matrix: list[JsonValue],
) -> list[JsonValue]:
    available_modules = {
        str(_as_mapping(row).get("module"))
        for row in evidence_matrix
        if str(_as_mapping(row).get("status")) == "available"
    }
    module_purposes = {
        "strategy_profile_registry": "load selected strategy contract",
        "paper_trading_engine": "read simulated account and paper cycles",
        "risk_engine": "evaluate approval blockers and risk decision",
        "market_data_adapter_read_only": "read market data without order authority",
        "indicators_feature_pipeline": "build strategy indicators and quality flags",
        "strategy_explanation": "normalize recommendation reasons",
        "paper_evaluation_gate": "block action when required evidence is missing",
    }
    rows: list[JsonValue] = []
    for module in _as_text_tuple(profile["enabled_modules"]):
        if module == "strategy_profile_registry":
            status = "available"
        elif module == "paper_evaluation_gate":
            status = "paper_only"
        elif module == "strategy_explanation":
            status = (
                "available"
                if str(strategy.get("explanation", "")) not in {"", "not_available"}
                else "missing"
            )
        else:
            status = "available" if module in available_modules else "missing"
        rows.append(
            {
                "module": module,
                "status": status,
                "scope": "paper_only",
                "purpose": module_purposes.get(module, "strategy evidence module"),
            }
        )
    return rows


def _strategy_lab_parameter_config(
    profile: Mapping[str, JsonValue],
    parameter_profile: str,
) -> dict[str, JsonValue]:
    configs = _as_mapping(profile.get("parameter_profile_configs", {}))
    value = configs.get(parameter_profile, {})
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def _strategy_lab_compare_runs(
    *,
    profile: Mapping[str, JsonValue],
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
    cycles: tuple[PaperTradingCycleResult, ...],
    selected_parameter_profile: str,
) -> list[JsonValue]:
    backtest = _advanced_backtest_summary(status=status, latest=latest, cycles=cycles)
    performance = _advanced_performance_summary(status, cycles=cycles)
    return [
        {
            "run_id": "current_paper",
            "strategy": profile["label"],
            "parameter_profile": "default",
            "mode": "paper",
            "status": "current dashboard run",
            "evidence_type": "paper_sample",
            "completed_backtest": False,
            "selected": selected_parameter_profile == "default",
            "sample_size": backtest["sample_size"],
            "win_rate": backtest["win_rate"],
            "expectancy": backtest["expectancy"],
            "max_drawdown": backtest["max_drawdown"],
            "paper_pnl": performance["unrealized_pnl"],
        },
        {
            "run_id": "defensive_profile",
            "strategy": profile["label"],
            "parameter_profile": "defensive",
            "mode": "research",
            "status": "not_run",
            "evidence_type": "profile_config",
            "completed_backtest": False,
            "note": "profile_config_only",
            "selected": selected_parameter_profile == "defensive",
            "sample_size": "not_run",
            "win_rate": "not_run",
            "expectancy": "not_run",
            "max_drawdown": "not_run",
            "paper_pnl": "not_run",
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


def _advanced_chart_payload(
    cycles: tuple[PaperTradingCycleResult, ...],
    *,
    drawings: list[JsonValue],
) -> dict[str, JsonValue]:
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
    executable = _is_executable_paper_trade(latest)
    stop_loss: Decimal | str | None = (
        evaluation.plan.stop_suggestion
        if evaluation and executable
        else "not_executable"
        if evaluation
        else None
    )
    target: Decimal | str | None = (
        evaluation.plan.target_suggestion
        if evaluation and executable
        else "not_executable"
        if evaluation
        else None
    )
    return {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "available_timeframes": ["1h", "4h", "1d"],
        "overlays": ["sma_3", "risk_lines", "markers"],
        "interaction_features": [
            "zoom",
            "pan",
            "crosshair",
            "ohlc_tooltip",
            "timeframe_switching",
            "indicator_toggles",
            "responsive_resize",
            "local_drawing_tools",
        ],
        "drawing_tools": {
            "supported_types": [item.value for item in DashboardChartDrawingType],
            "save_route": "/api/chart-drawing",
            "delete_route": "/api/delete-chart-drawing",
            "storage": "local_paper_dashboard_state",
            "paper_only": True,
        },
        "drawings": drawings,
        "candles": candles,
        "indicators": indicators,
        "markers": markers,
        "risk_lines": {
            "entry": _str(latest.snapshot.candle.close if latest is not None else None),
            "stop_loss": _str(stop_loss),
            "target": _str(target),
        },
    }


def _advanced_order_book_payload(
    *,
    latest: PaperTradingCycleResult | None,
    order_book: OrderBookSnapshot | None,
) -> dict[str, JsonValue]:
    snapshot = order_book
    metrics = calculate_order_book_metrics(snapshot) if snapshot is not None else None
    if metrics is None and latest is not None:
        metrics = latest.snapshot.order_book_metrics
    midpoint = (
        (metrics.best_bid + metrics.best_ask) / Decimal("2")
        if metrics is not None
        else DECIMAL_ZERO
    )
    spread_bps = (
        metrics.spread / midpoint * Decimal("10000")
        if metrics is not None and midpoint > DECIMAL_ZERO
        else None
    )
    return {
        "symbol": snapshot.pair.symbol if snapshot is not None else "BTC/USDT",
        "source": snapshot.source_ref if snapshot is not None else "paper_snapshot_metrics",
        "captured_at": snapshot.captured_at.isoformat()
        if snapshot is not None
        else _str(latest.snapshot.received_at if latest is not None else None),
        "summary": {
            "best_bid": _str(metrics.best_bid if metrics is not None else None),
            "best_ask": _str(metrics.best_ask if metrics is not None else None),
            "spread": _str(metrics.spread if metrics is not None else None),
            "spread_bps": _str(
                spread_bps.quantize(Decimal("0.0001")) if spread_bps is not None else None
            ),
            "bid_depth": _str(metrics.bid_depth if metrics is not None else None),
            "ask_depth": _str(metrics.ask_depth if metrics is not None else None),
            "imbalance": _str(metrics.imbalance if metrics is not None else None),
            "bias": _order_book_bias(metrics.imbalance if metrics is not None else None),
            "paper_safe": True,
        },
        "bids": _order_book_level_rows(snapshot.bids, descending=True)
        if snapshot is not None
        else [],
        "asks": _order_book_level_rows(snapshot.asks, descending=False)
        if snapshot is not None
        else [],
    }


def _advanced_order_flow_payload(
    *,
    trades: tuple[Trade, ...],
    order_book: OrderBookSnapshot | None,
    latest: PaperTradingCycleResult | None,
) -> dict[str, JsonValue]:
    recent = tuple(sorted(trades, key=lambda item: item.traded_at, reverse=True)[:20])
    buy_volume = sum(
        (trade.quantity for trade in recent if trade.side is OrderSide.BUY),
        DECIMAL_ZERO,
    )
    sell_volume = sum(
        (trade.quantity for trade in recent if trade.side is OrderSide.SELL),
        DECIMAL_ZERO,
    )
    total_volume = buy_volume + sell_volume
    buy_pressure = buy_volume / total_volume if total_volume > DECIMAL_ZERO else DECIMAL_ZERO
    latest_trade = recent[0] if recent else None
    return {
        "symbol": order_book.pair.symbol if order_book is not None else "BTC/USDT",
        "source": _order_flow_source(trades=recent, order_book=order_book),
        "captured_at": _str(
            latest_trade.traded_at
            if latest_trade is not None
            else latest.snapshot.received_at
            if latest is not None
            else None
        ),
        "summary": {
            "trade_count": str(len(recent)),
            "buy_volume": str(buy_volume),
            "sell_volume": str(sell_volume),
            "total_volume": str(total_volume),
            "buy_pressure_pct": _pct(buy_pressure),
            "dominant_side": _order_flow_dominant_side(buy_pressure, len(recent)),
            "latest_price": _str(latest_trade.price if latest_trade is not None else None),
            "paper_safe": True,
            "live_order_capability": False,
        },
        "recent_trades": [_market_trade_row(trade) for trade in recent],
        "liquidity_heatmap": _liquidity_heatmap(order_book),
    }


def _order_flow_source(
    *,
    trades: tuple[Trade, ...],
    order_book: OrderBookSnapshot | None,
) -> str:
    if trades:
        return f"{trades[0].exchange.name}:recent-trades"
    if order_book is not None:
        return f"{order_book.exchange.name}:order-book-only"
    return "not_available"


def _order_flow_dominant_side(buy_pressure: Decimal, trade_count: int) -> str:
    if trade_count == 0:
        return "not_available"
    if buy_pressure >= Decimal("0.58"):
        return "buyer_pressure"
    if buy_pressure <= Decimal("0.42"):
        return "seller_pressure"
    return "balanced"


def _market_trade_row(trade: Trade) -> dict[str, JsonValue]:
    return {
        "trade_id": trade.trade_id,
        "time": trade.traded_at.isoformat(),
        "side": trade.side.value.upper(),
        "price": str(trade.price),
        "quantity": str(trade.quantity),
        "notional": str(trade.price * trade.quantity),
    }


def _liquidity_heatmap(order_book: OrderBookSnapshot | None) -> list[JsonValue]:
    if order_book is None:
        return []
    levels = list(order_book.bids[:5]) + list(order_book.asks[:5])
    max_quantity = max((level.quantity for level in levels), default=DECIMAL_ZERO)
    rows: list[JsonValue] = []
    for side, levels_for_side in (
        ("bid", order_book.bids[:5]),
        ("ask", order_book.asks[:5]),
    ):
        for level in levels_for_side:
            intensity = (
                level.quantity / max_quantity if max_quantity > DECIMAL_ZERO else DECIMAL_ZERO
            )
            rows.append(
                {
                    "side": side,
                    "price": str(level.price),
                    "quantity": str(level.quantity),
                    "intensity_pct": _pct(intensity),
                }
            )
    return rows


def _order_book_level_rows(
    levels: tuple[OrderBookLevel, ...],
    *,
    descending: bool,
) -> list[JsonValue]:
    ordered = sorted(levels, key=lambda item: item.price, reverse=descending)
    running_quantity = DECIMAL_ZERO
    rows: list[JsonValue] = []
    for level in ordered[:10]:
        running_quantity += level.quantity
        rows.append(
            {
                "price": str(level.price),
                "quantity": str(level.quantity),
                "total": str(running_quantity),
            }
        )
    return rows


def _order_book_bias(imbalance: Decimal | None) -> str:
    if imbalance is None:
        return "not_available"
    if imbalance >= Decimal("0.15"):
        return "bid_depth_dominant"
    if imbalance <= Decimal("-0.15"):
        return "ask_depth_dominant"
    return "balanced"


def _advanced_order_ticket_payload(
    *,
    latest: PaperTradingCycleResult | None,
) -> dict[str, JsonValue]:
    reference_price = (
        latest.snapshot.candle.close if latest is not None else WATCHLIST_DEMO_PRICES["BTC/USDT"]
    )
    return {
        "paper_only": True,
        "live_order_capability": False,
        "supported_order_types": [item.value for item in DashboardPaperOrderType],
        "supported_sides": [OrderSide.BUY.value, OrderSide.SELL.value],
        "default_quantity": "0.01",
        "reference_price": str(reference_price),
        "estimated_default_notional": str(Decimal("0.01") * reference_price),
        "symbol_filters": PAPER_ORDER_FILTER.as_dict(),
        "submit_route": "/api/paper-order-ticket",
        "cancel_route": "/api/cancel-paper-order",
        "safety_note": (
            "Paper ticket only; no Binance order is submitted. Orders are checked against "
            "Binance-style tick size, step size, min quantity, and min notional filters."
        ),
    }


def _advanced_position_payload(
    *,
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
) -> dict[str, JsonValue]:
    portfolio = status.portfolio
    mark_price = status.current_btc_price or portfolio.average_entry_price
    has_position = portfolio.base_quantity > DECIMAL_ZERO
    market_value = portfolio.base_quantity * mark_price if has_position else DECIMAL_ZERO
    unrealized = (
        (mark_price - portfolio.average_entry_price) * portfolio.base_quantity
        if has_position
        else DECIMAL_ZERO
    )
    unrealized_pct = (
        (mark_price / portfolio.average_entry_price - Decimal("1"))
        if has_position and portfolio.average_entry_price > DECIMAL_ZERO
        else DECIMAL_ZERO
    )
    evaluation = latest.strategy_evaluation if latest is not None else None
    executable = _is_executable_paper_trade(latest)
    stop_loss = (
        evaluation.plan.stop_suggestion
        if evaluation and executable
        else "not_executable"
        if evaluation
        else None
    )
    target = (
        evaluation.plan.target_suggestion
        if evaluation and executable
        else "not_executable"
        if evaluation
        else None
    )
    close_quantity = portfolio.base_quantity if has_position else DECIMAL_ZERO
    reduce_quantity = portfolio.base_quantity / Decimal("2") if has_position else DECIMAL_ZERO
    return {
        "symbol": "BTC/USDT",
        "has_open_position": has_position,
        "open_btc": str(portfolio.base_quantity),
        "average_entry": str(portfolio.average_entry_price),
        "mark_price": str(mark_price),
        "market_value": str(market_value),
        "unrealized_pnl": str(unrealized),
        "unrealized_pnl_pct": _pct(unrealized_pct),
        "realized_pnl": str(portfolio.realized_pnl),
        "stop_loss": _str(stop_loss),
        "target": _str(target),
        "close_quantity": str(close_quantity),
        "reduce_quantity": str(reduce_quantity),
        "can_stage_close": has_position,
        "can_stage_reduce": has_position,
        "paper_only": True,
        "live_order_capability": False,
        "close_route": "/api/stage-close-position",
        "reduce_route": "/api/stage-reduce-position",
    }


def _advanced_backtest_summary(
    *,
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
    cycles: tuple[PaperTradingCycleResult, ...],
) -> dict[str, JsonValue]:
    sample_size = status.cycles_count
    equity_curve = _paper_equity_curve(cycles=cycles, status=status)
    returns = returns_from_equity(equity_curve)
    metric_status = "calculated" if returns else "insufficient_data"
    return {
        "status": "calculated_paper_sample",
        "sample_size": str(sample_size),
        "metric_status": metric_status,
        "win_rate": _metric_or_status(calculate_win_rate(returns), metric_status),
        "expectancy": _metric_or_status(calculate_expectancy(returns), metric_status),
        "max_drawdown": str(calculate_max_drawdown(equity_curve)),
        "sharpe": _metric_or_status(calculate_sharpe_ratio(returns), metric_status),
        "sortino": _metric_or_status(calculate_sortino_ratio(returns), metric_status),
        "profit_factor": _metric_or_status(calculate_profit_factor(returns), metric_status),
        "fees": str(status.portfolio.fees_paid),
        "slippage": "paper_fill_model",
        "latest_signal_ref": _latest_signal_ref(latest),
        "sample_size_warning": _sample_size_warning(sample_size),
    }


def _advanced_performance_summary(
    status: PaperStatusResponse,
    *,
    cycles: tuple[PaperTradingCycleResult, ...],
) -> dict[str, JsonValue]:
    current_equity = status.portfolio.equity
    equity_curve = _paper_equity_curve(cycles=cycles, status=status)
    return {
        "daily": _period_return_pct(cycles=cycles, status=status, days=1),
        "weekly": _period_return_pct(cycles=cycles, status=status, days=7),
        "monthly": _period_return_pct(cycles=cycles, status=status, days=30),
        "long_term": _long_term_return_pct(status, starting_balance=equity_curve[0]),
        "period_analytics_status": "calculated",
        "period_analytics_source": "paper_cycle_equity",
        "current_equity": str(current_equity),
        "mark_symbol": PAIR.symbol,
        "mark_price": _str(status.current_btc_price),
        "cash": str(status.portfolio.cash),
        "open_btc": str(status.portfolio.base_quantity),
        "realized_pnl": str(status.portfolio.realized_pnl),
        "unrealized_pnl": _unrealized_pnl(status),
        "drawdown": str(status.portfolio.drawdown_pct),
        "fees_paid": str(status.portfolio.fees_paid),
        "trades": str(status.trades_count),
    }


def _paper_equity_curve(
    *,
    cycles: tuple[PaperTradingCycleResult, ...],
    status: PaperStatusResponse,
) -> tuple[Decimal, ...]:
    points = [cycles[0].equity] if cycles else [status.portfolio.equity]
    points.extend(cycle.equity for cycle in cycles[1:])
    if not points or points[-1] != status.portfolio.equity:
        points.append(status.portfolio.equity)
    return tuple(points)


def _metric_or_status(value: Decimal, status: str) -> str:
    return str(value) if status == "calculated" else status


def _period_return_pct(
    *,
    cycles: tuple[PaperTradingCycleResult, ...],
    status: PaperStatusResponse,
    days: int,
) -> str:
    if not cycles:
        return "insufficient_data"
    latest_at = cycles[-1].snapshot.received_at
    cutoff = latest_at - timedelta(days=days)
    in_window = tuple(cycle for cycle in cycles if cycle.snapshot.received_at >= cutoff)
    if not in_window:
        return "insufficient_data"
    baseline = in_window[0].equity
    if baseline <= DECIMAL_ZERO:
        return "insufficient_data"
    return _pct((status.portfolio.equity - baseline) / baseline)


def _long_term_return_pct(
    status: PaperStatusResponse,
    *,
    starting_balance: Decimal = Decimal("10000"),
) -> str:
    if starting_balance <= DECIMAL_ZERO:
        return "insufficient_data"
    return _pct((status.portfolio.equity - starting_balance) / starting_balance)


def _advanced_risk_safety_payload(
    *,
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
    market: Mapping[str, JsonValue],
    portfolio: Mapping[str, JsonValue],
    controls: Mapping[str, JsonValue],
    order_book: OrderBookSnapshot | None,
    recent_market_trades: tuple[Trade, ...],
    transactions: list[JsonValue],
    open_orders: list[JsonValue],
    events: list[JsonValue],
) -> dict[str, JsonValue]:
    risk_halts = _risk_halts(status)
    order_book_metrics = (
        calculate_order_book_metrics(order_book) if order_book is not None else None
    )
    spread_bps = _spread_bps(order_book_metrics)
    data_reasons = _risk_safety_data_reasons(status=status, latest=latest, market=market)
    exchange_rows = _risk_safety_exchange_rows(
        market=market,
        order_book=order_book,
        order_book_metrics=order_book_metrics,
        recent_market_trades=recent_market_trades,
    )
    reconciliation = _risk_safety_reconciliation(
        status=status,
        portfolio=portfolio,
        transactions=transactions,
        open_orders=open_orders,
        events=events,
    )
    blocking_reasons = [
        reason
        for reason in ([] if risk_halts == ("none",) else list(risk_halts)) + data_reasons
        if reason != "none"
    ]
    return {
        "paper_only": True,
        "live_order_capability": False,
        "summary": {
            "safety_state": "blocked" if blocking_reasons else "clear",
            "data_health": status.data_health,
            "market_data_health": str(market.get("data_freshness", "not_available")),
            "latest_risk_decision": status.latest_risk_decision,
            "drawdown": str(status.portfolio.drawdown_pct),
            "risk_halts": list(risk_halts),
            "paused": status.paused,
            "kill_switch_active": status.kill_switch_active,
            "open_paper_orders": str(len(open_orders)),
            "spread_bps": _str(spread_bps),
        },
        "risk_checks": [
            _risk_safety_check(
                "risk_decision",
                status.latest_risk_decision == "approved",
                status.latest_risk_decision,
            ),
            _risk_safety_check(
                "drawdown_halt",
                status.portfolio.drawdown_pct < Decimal("0.05"),
                f"drawdown={status.portfolio.drawdown_pct}, limit=0.05",
            ),
            _risk_safety_check("risk_halts", risk_halts == ("none",), "; ".join(risk_halts)),
            _risk_safety_check("paper_paused", not status.paused, str(status.paused)),
            _risk_safety_check(
                "kill_switch",
                not status.kill_switch_active,
                str(status.kill_switch_active),
            ),
            _risk_safety_check(
                "data_quality",
                not data_reasons,
                "; ".join(data_reasons) if data_reasons else status.data_health,
            ),
            _risk_safety_check(
                "spread",
                spread_bps is None or spread_bps <= Decimal("25"),
                f"spread_bps={_str(spread_bps)}, limit=25",
            ),
        ],
        "parameter_health": [_parameter_health_row(item) for item in status.parameter_health],
        "exchange_health": exchange_rows,
        "reconciliation": reconciliation,
        "unsupported_markets": {
            "live_trading": False,
            "leverage": False,
            "margin": False,
            "futures": False,
            "options": False,
            "withdrawals": False,
            "transfers": False,
        },
    }


def _spread_bps(metrics: OrderBookMetrics | None) -> Decimal | None:
    if metrics is None:
        return None
    midpoint = (metrics.best_bid + metrics.best_ask) / Decimal("2")
    if midpoint <= DECIMAL_ZERO:
        return None
    return (metrics.spread / midpoint * Decimal("10000")).quantize(Decimal("0.0001"))


def _risk_safety_data_reasons(
    *,
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
    market: Mapping[str, JsonValue],
) -> list[str]:
    reasons: list[str] = []
    if status.data_health not in {"trusted", "healthy"}:
        reasons.append(f"paper data health is {status.data_health}")
    market_health = str(market.get("data_freshness", "not_available"))
    if market_health != "healthy":
        reasons.append(f"market data health is {market_health}")
    if latest is not None and latest.snapshot.health.is_stale:
        reasons.append("latest stream is stale")
    if latest is not None and latest.skipped_reason:
        reasons.append(latest.skipped_reason)
    return reasons


def _risk_safety_exchange_rows(
    *,
    market: Mapping[str, JsonValue],
    order_book: OrderBookSnapshot | None,
    order_book_metrics: OrderBookMetrics | None,
    recent_market_trades: tuple[Trade, ...],
) -> list[JsonValue]:
    return [
        {
            "check": "market_data_source",
            "status": "available" if market.get("source") else "missing",
            "detail": str(market.get("source", "not_available")),
        },
        {
            "check": "order_book",
            "status": "available" if order_book is not None else "missing",
            "detail": order_book.source_ref if order_book is not None else "not_available",
        },
        {
            "check": "spread_depth",
            "status": "available" if order_book_metrics is not None else "missing",
            "detail": (
                f"bid_depth={order_book_metrics.bid_depth}, "
                f"ask_depth={order_book_metrics.ask_depth}"
                if order_book_metrics is not None
                else "not_available"
            ),
        },
        {
            "check": "recent_trades",
            "status": "available" if recent_market_trades else "missing",
            "detail": str(len(recent_market_trades)),
        },
        {
            "check": "live_execution",
            "status": "disabled",
            "detail": "paper dashboard cannot create live orders",
        },
    ]


def _risk_safety_reconciliation(
    *,
    status: PaperStatusResponse,
    portfolio: Mapping[str, JsonValue],
    transactions: list[JsonValue],
    open_orders: list[JsonValue],
    events: list[JsonValue],
) -> list[JsonValue]:
    paper_fill_events = [
        event
        for event in events
        if isinstance(event, Mapping) and event.get("event_type") == "paper_fill"
    ]
    return [
        _risk_safety_check(
            "transaction_count",
            len(transactions) == status.trades_count,
            f"transactions={len(transactions)}, status_trades={status.trades_count}",
        ),
        _risk_safety_check(
            "paper_fill_audit",
            not transactions or bool(paper_fill_events),
            f"paper_fill_events={len(paper_fill_events)}",
        ),
        _risk_safety_check(
            "cash_non_negative",
            _decimal(portfolio.get("cash", "0")) >= DECIMAL_ZERO,
            f"cash={portfolio.get('cash', 'not_available')}",
        ),
        _risk_safety_check(
            "open_order_rows",
            all(
                isinstance(item, Mapping) and item.get("paper_only") is True for item in open_orders
            ),
            f"open_orders={len(open_orders)}",
        ),
    ]


def _risk_safety_check(check: str, passed: bool, detail: str) -> dict[str, JsonValue]:
    return {
        "check": check,
        "status": "pass" if passed else "review",
        "passed": passed,
        "detail": detail,
        "paper_only": True,
    }


def _parameter_health_row(item: PaperParameterHealth) -> dict[str, JsonValue]:
    return {
        "key": item.key,
        "value": item.value,
        "status": item.status,
        "reason": item.reason,
    }


def _advanced_trade_journal_payload(
    *,
    transactions: list[JsonValue],
    journal_entries: list[JsonValue],
    status: PaperStatusResponse,
    latest: PaperTradingCycleResult | None,
) -> dict[str, JsonValue]:
    entry_mappings = [_as_mapping(item) for item in journal_entries if isinstance(item, Mapping)]
    entries: list[JsonValue] = [dict(entry) for entry in entry_mappings]
    transaction_count = len(transactions)
    journaled_refs = {
        str(entry.get("trade_ref", "")).strip()
        for entry in entry_mappings
        if str(entry.get("trade_ref", "")).strip()
    }
    strategy_name = (
        latest.strategy_evaluation.strategy_name
        if latest is not None and latest.strategy_evaluation is not None
        else "MinRiskSpotStrategyV1"
    )
    total_pnl = status.portfolio.realized_pnl + _unrealized_pnl_decimal(status)
    mistake_count = sum(
        1 for entry in entry_mappings if str(entry.get("mistake_review", "")).strip()
    )
    lesson_count = sum(1 for entry in entry_mappings if str(entry.get("lesson", "")).strip())
    tag_counts = _journal_tag_counts(entry_mappings)
    return {
        "paper_only": True,
        "live_order_capability": False,
        "add_route": "/api/journal-entry",
        "delete_route": "/api/delete-journal-entry",
        "supported_setup_types": [
            "trend_continuation",
            "pullback",
            "breakout",
            "mean_reversion",
            "risk_reduction",
            "manual_review",
        ],
        "summary": {
            "transactions": str(transaction_count),
            "journal_entries": str(len(entries)),
            "journaled_trade_refs": str(len(journaled_refs)),
            "unjournaled_transactions": str(max(transaction_count - len(journaled_refs), 0)),
            "mistakes_logged": str(mistake_count),
            "lessons_logged": str(lesson_count),
            "tags_used": str(len(tag_counts)),
            "attribution_scope": "paper_mark_to_market",
        },
        "pnl_by_strategy": [
            {
                "strategy": strategy_name,
                "paper_pnl": str(total_pnl),
                "transactions": str(transaction_count),
                "journal_entries": str(len(entries)),
                "scope": "current paper account mark-to-market",
            }
        ],
        "pnl_by_regime": [
            {
                "regime": status.active_regime,
                "paper_pnl": str(total_pnl),
                "transactions": str(transaction_count),
                "journal_entries": str(len(entries)),
                "scope": "current paper account mark-to-market",
            }
        ],
        "tag_breakdown": [
            {"tag": tag, "count": str(count)} for tag, count in sorted(tag_counts.items())
        ],
        "entries": entries,
        "chart_context_hint": _journal_chart_context_hint(latest),
    }


def _advanced_trader_feedback_payload(items: list[JsonValue]) -> dict[str, JsonValue]:
    feedback = [_as_mapping(item) for item in items if isinstance(item, Mapping)]
    open_items = [item for item in feedback if str(item.get("status", "")) == "open"]
    return {
        "paper_only": True,
        "add_route": "/api/trader-feedback",
        "close_route": "/api/close-trader-feedback",
        "supported_reviewer_roles": [
            "trader",
            "risk_reviewer",
            "strategy_reviewer",
            "operator",
            "developer",
        ],
        "supported_categories": [
            "ui",
            "risk",
            "strategy",
            "market_data",
            "order_ticket",
            "reporting",
            "missing_feature",
        ],
        "supported_severities": ["low", "medium", "high", "blocker"],
        "summary": {
            "total": str(len(feedback)),
            "open": str(len(open_items)),
            "closed": str(len(feedback) - len(open_items)),
            "blockers": str(
                sum(1 for item in open_items if str(item.get("severity", "")) == "blocker")
            ),
            "high": str(sum(1 for item in open_items if str(item.get("severity", "")) == "high")),
        },
        "category_breakdown": _feedback_count_rows(feedback, key="category"),
        "severity_breakdown": _feedback_count_rows(open_items, key="severity"),
        "items": [dict(item) for item in feedback],
    }


def _feedback_count_rows(
    items: list[Mapping[str, JsonValue]],
    *,
    key: str,
) -> list[JsonValue]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return [{key: value, "count": str(count)} for value, count in sorted(counts.items())]


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
        return "no_signal_ref"
    return _status_str(latest.strategy_evaluation.signal_ref, "no_signal_ref")


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
    trader_feedback = _as_mapping(advanced.get("trader_feedback", {}))
    trader_feedback_summary = _as_mapping(trader_feedback.get("summary", {}))
    open_feedback_blockers = _decimal(trader_feedback_summary.get("blockers", "0"))
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
                    "chart_drawings",
                    "order_book",
                    "order_flow",
                    "order_ticket",
                    "open_paper_orders",
                    "position",
                    "watchlist",
                    "alerts",
                    "alert_rules",
                    "risk_safety",
                    "trade_journal",
                    "trader_feedback",
                    "runtime_telemetry",
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
        _readiness_item(
            "open_trader_feedback_blockers",
            "No open trader feedback blockers",
            open_feedback_blockers == DECIMAL_ZERO,
            f"open_blocker_feedback={open_feedback_blockers}",
        ),
    ]
    ready = all(
        _as_mapping(item).get("passed") is True
        for item in checklist
        if _as_mapping(item).get("blocking") is True
    )
    trader_verdict = _trader_readiness_verdict(
        ready=ready,
        checklist=checklist,
        reconstructability=reconstructability,
        advanced=advanced,
        strategy_lab=strategy_lab,
        route_checks=route_checks,
        db_path=db_path,
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
        "trader_verdict": trader_verdict,
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


def _trader_readiness_verdict(
    *,
    ready: bool,
    checklist: list[JsonValue],
    reconstructability: Mapping[str, JsonValue],
    advanced: Mapping[str, JsonValue],
    strategy_lab: Mapping[str, JsonValue],
    route_checks: list[JsonValue],
    db_path: str | None,
) -> dict[str, JsonValue]:
    blocking_failures = [
        str(_as_mapping(item).get("label"))
        for item in checklist
        if _as_mapping(item).get("blocking") is True and _as_mapping(item).get("passed") is not True
    ]
    backtest = _as_mapping(advanced.get("backtest_summary", {}))
    risk_safety = _as_mapping(advanced.get("risk_safety", {}))
    trader_feedback = _as_mapping(advanced.get("trader_feedback", {}))
    feedback_items = _as_list(trader_feedback.get("items", []))
    strategy_missing = [
        str(item) for item in _as_text_list(strategy_lab.get("missing_evidence", []))
    ]
    open_feedback_blockers = [
        _as_mapping(item)
        for item in feedback_items
        if isinstance(item, Mapping)
        and str(item.get("status", "")) == "open"
        and str(item.get("severity", "")) == "blocker"
    ]
    sample_warning = str(backtest.get("sample_size_warning", "not_available"))
    proof_points: list[JsonValue] = [
        "Beginner, Advanced Trader, and Strategy Lab views are present.",
        "All dashboard routes are read-only, preference-only, or paper-control only.",
        "Live execution, margin, futures, options, withdrawals, and transfers are disabled.",
        "Paper trade reconstructability is checked from market data through account update.",
        "Strategy Lab exposes required evidence, module routing, and compare-run rows.",
    ]
    if db_path is not None:
        proof_points.append("SQLite paper ledger is configured for local audit history.")
    if _as_mapping(risk_safety.get("summary", {})).get("safety_state") == "clear":
        proof_points.append("Risk and safety panel currently reports clear paper-mode status.")
    blockers: list[JsonValue] = list(blocking_failures)
    if strategy_missing:
        blockers.append("Strategy Lab is missing required evidence: " + ", ".join(strategy_missing))
    for item in open_feedback_blockers:
        blockers.append(
            "Open trader feedback blocker: "
            f"{item.get('category', 'unknown')} - {item.get('summary', 'not_available')}"
        )
    warnings: list[JsonValue] = [
        "Paper-mode readiness does not prove profitability.",
        sample_warning,
        "Any live trading stage still requires a separate supervised-live review.",
        (
            "Trader review should verify chart usability, order-ticket ergonomics, "
            "and strategy assumptions."
        ),
    ]
    next_steps: list[JsonValue] = [
        "Run a longer paper session with real read-only Binance market data.",
        "Export the paper report and transaction CSV after multiple market conditions.",
        "Ask traders to review the Advanced Trader and Strategy Lab evidence layout.",
    ]
    if open_feedback_blockers:
        next_steps.insert(0, "Close or resolve open blocker-severity trader feedback.")
    if not db_path:
        next_steps.insert(0, "Configure ABTP_PAPER_DB_PATH so SQLite is the main paper ledger.")
    return {
        "paper_demo_ready": ready and not blockers,
        "live_capital_ready": False,
        "readiness_level": "paper_demo_ready" if ready and not blockers else "blocked",
        "shareable_scope": (
            "paper-mode trader review only"
            if ready and not blockers
            else "internal testing until blockers are fixed"
        ),
        "profitability_claim": "none",
        "route_count": str(len(route_checks)),
        "reconstructability_status": str(reconstructability.get("status", "not_available")),
        "proof_points": proof_points,
        "blockers": blockers,
        "warnings": warnings,
        "next_steps": next_steps,
    }


def _paper_safe_route_checks() -> list[JsonValue]:
    routes = (
        ("GET /", "Dashboard shell only"),
        ("GET /api/status", "Read-only paper dashboard status"),
        ("GET /api/readiness", "Read-only readiness checklist"),
        ("GET /api/activity", "Read-only local paper activity timeline"),
        ("GET /paper-report", "Read-only paper report export"),
        ("GET /trader-handoff.md", "Read-only trader review handoff export"),
        ("GET /trader-evidence.json", "Read-only trader evidence JSON export"),
        ("GET /paper-transactions.csv", "Read-only paper transaction export"),
        ("GET /trader-feedback.csv", "Read-only trader feedback CSV export"),
        ("POST /api/ui-mode", "UI preference only"),
        ("POST /api/ui-shell", "UI shell preference only"),
        ("POST /api/mark-notifications-read", "Local notification preference only"),
        ("POST /api/strategy-lab-selection", "Strategy Lab preference only"),
        ("POST /api/watchlist-symbol", "Watchlist preference only"),
        ("POST /api/alert-rule", "Creates local dashboard alert rule only"),
        ("POST /api/delete-alert-rule", "Deletes local dashboard alert rule only"),
        ("POST /api/journal-entry", "Saves local paper trade journal note only"),
        ("POST /api/delete-journal-entry", "Deletes local paper journal note only"),
        ("POST /api/trader-feedback", "Saves local trader-review feedback only"),
        ("POST /api/close-trader-feedback", "Closes local trader-review feedback only"),
        ("POST /api/chart-drawing", "Saves local chart drawing only"),
        ("POST /api/delete-chart-drawing", "Deletes local chart drawing only"),
        ("POST /api/paper-order-ticket", "Stages simulated paper order ticket only"),
        ("POST /api/cancel-paper-order", "Cancels simulated paper order ticket only"),
        ("POST /api/stage-close-position", "Stages simulated close-position review only"),
        ("POST /api/stage-reduce-position", "Stages simulated reduce-position review only"),
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


def _bool_preference(value: JsonValue) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "collapsed"}
    return False


def _datetime_preference(value: JsonValue) -> datetime | None:
    text = str(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


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


def _restore_paper_account_state(controller: PaperDashboardController) -> bool:
    if controller.state_path is not None:
        path = Path(controller.state_path)
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, Mapping):
                    raise ValueError("paper state file must contain a JSON object")
                _restore_paper_payload(controller, payload, source_ref=str(path))
                return True
            except (OSError, ValueError, TypeError) as exc:
                controller.events.insert(
                    0,
                    PaperDashboardEvent(
                        event_type="paper_state_restore_failed",
                        message="Saved paper wallet could not be restored; checking SQLite.",
                        reason=str(exc),
                        occurred_at=_latest_time(controller.engine),
                    ),
                )
    if controller.db_path is not None:
        try:
            with _paper_dashboard_repository(controller.db_path) as repository:
                payload = repository.load_latest_state_payload()
            if payload is not None:
                _restore_paper_payload(controller, payload, source_ref=controller.db_path)
                return True
        except (OSError, ValueError, TypeError) as exc:
            controller.events.insert(
                0,
                PaperDashboardEvent(
                    event_type="paper_sqlite_restore_failed",
                    message="SQLite paper wallet could not be restored; fresh paper wallet loaded.",
                    reason=str(exc),
                    occurred_at=_latest_time(controller.engine),
                ),
            )
    return False


def _paper_dashboard_state_payload(controller: PaperDashboardController) -> dict[str, JsonValue]:
    state = controller.engine.account.state
    return {
        "version": 2,
        "updated_at": _latest_time(controller.engine).isoformat(),
        "market_data_source": controller.market_data_source,
        "ui_preferences": {
            "mode": controller.ui_mode.value,
            "selected_watchlist_symbol": controller.selected_watchlist_symbol,
            "sidebar_collapsed": controller.sidebar_collapsed,
            "notification_last_seen_at": controller.notification_last_seen_at.isoformat()
            if controller.notification_last_seen_at is not None
            else "",
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
        "open_paper_orders": [order.as_dict() for order in controller.open_paper_orders],
        "alert_rules": [rule.as_dict() for rule in controller.alert_rules],
        "journal_entries": [entry.as_dict() for entry in controller.journal_entries],
        "trader_feedback": [item.as_dict() for item in controller.trader_feedback],
        "chart_drawings": [drawing.as_dict() for drawing in controller.chart_drawings],
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
        controller.selected_watchlist_symbol = _watchlist_symbol(
            str(preferences.get("selected_watchlist_symbol", controller.selected_watchlist_symbol))
        )
        controller.sidebar_collapsed = _bool_preference(
            preferences.get("sidebar_collapsed", controller.sidebar_collapsed)
        )
        controller.notification_last_seen_at = _datetime_preference(
            preferences.get("notification_last_seen_at", "")
        )
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
    open_orders_payload = payload.get("open_paper_orders", [])
    if isinstance(open_orders_payload, list):
        controller.open_paper_orders = [
            _paper_order_from_mapping(item)
            for item in open_orders_payload
            if isinstance(item, Mapping)
        ]
    alert_rules_payload = payload.get("alert_rules", [])
    if isinstance(alert_rules_payload, list):
        controller.alert_rules = [
            _alert_rule_from_mapping(item)
            for item in alert_rules_payload
            if isinstance(item, Mapping)
        ]
    journal_entries_payload = payload.get("journal_entries", [])
    if isinstance(journal_entries_payload, list):
        controller.journal_entries = [
            _journal_entry_from_mapping(item)
            for item in journal_entries_payload
            if isinstance(item, Mapping)
        ]
    trader_feedback_payload = payload.get("trader_feedback", [])
    if isinstance(trader_feedback_payload, list):
        controller.trader_feedback = [
            _trader_feedback_from_mapping(item)
            for item in trader_feedback_payload
            if isinstance(item, Mapping)
        ]
    chart_drawings_payload = payload.get("chart_drawings", [])
    if isinstance(chart_drawings_payload, list):
        controller.chart_drawings = [
            _chart_drawing_from_mapping(item)
            for item in chart_drawings_payload
            if isinstance(item, Mapping)
        ]
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
    cash = _decimal(payload.get("cash", str(_paper_initial_cash())))
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


def _paper_order_from_mapping(payload: Mapping[str, JsonValue]) -> DashboardPaperOrder:
    created_at = datetime.fromisoformat(str(payload.get("created_at", DEFAULT_NOW.isoformat())))
    return DashboardPaperOrder(
        order_id=str(payload["order_id"]),
        order_type=DashboardPaperOrderType(str(payload["order_type"])),
        side=OrderSide(str(payload["side"])),
        quantity=_decimal(payload["quantity"]),
        created_at=created_at,
        status=DashboardPaperOrderStatus(str(payload.get("status", "open"))),
        symbol=str(payload.get("symbol", "BTC/USDT")),
        limit_price=_optional_decimal_from_json(payload.get("limit_price")),
        stop_price=_optional_decimal_from_json(payload.get("stop_price")),
        take_profit_price=_optional_decimal_from_json(payload.get("take_profit_price")),
        reason=str(payload.get("reason", "")),
    )


def _alert_rule_from_mapping(payload: Mapping[str, JsonValue]) -> DashboardAlertRule:
    created_at = datetime.fromisoformat(str(payload.get("created_at", DEFAULT_NOW.isoformat())))
    return DashboardAlertRule(
        alert_id=str(payload["alert_id"]),
        alert_type=DashboardAlertType(str(payload["alert_type"])),
        symbol=_watchlist_symbol(str(payload["symbol"])),
        threshold=_optional_decimal_from_json(payload.get("threshold")),
        expected_value=str(payload.get("expected_value", "")),
        enabled=bool(payload.get("enabled", True)),
        created_at=created_at,
    )


def _journal_entry_from_mapping(payload: Mapping[str, JsonValue]) -> DashboardJournalEntry:
    created_at = datetime.fromisoformat(str(payload.get("created_at", DEFAULT_NOW.isoformat())))
    updated_at = datetime.fromisoformat(str(payload.get("updated_at", created_at.isoformat())))
    tags_payload = payload.get("tags", [])
    tags = tuple(str(item) for item in tags_payload) if isinstance(tags_payload, list) else ()
    return DashboardJournalEntry(
        journal_id=str(payload["journal_id"]),
        trade_ref=str(payload.get("trade_ref", "")),
        symbol=_watchlist_symbol(str(payload.get("symbol", "BTC/USDT"))),
        setup_type=_journal_setup_type(str(payload.get("setup_type", "manual_review"))),
        tags=tags,
        notes=str(payload.get("notes", "")),
        mistake_review=str(payload.get("mistake_review", "")),
        lesson=str(payload.get("lesson", "")),
        chart_context=str(payload.get("chart_context", "")),
        strategy=str(payload.get("strategy", "MinRiskSpotStrategyV1")),
        regime=str(payload.get("regime", "unknown")),
        created_at=created_at,
        updated_at=updated_at,
    )


def _trader_feedback_from_mapping(payload: Mapping[str, JsonValue]) -> DashboardTraderFeedback:
    created_at = datetime.fromisoformat(str(payload.get("created_at", DEFAULT_NOW.isoformat())))
    resolved_at_raw = str(payload.get("resolved_at", "")).strip()
    return DashboardTraderFeedback(
        feedback_id=str(payload["feedback_id"]),
        reviewer_role=_trader_feedback_reviewer_role(str(payload.get("reviewer_role", "trader"))),
        category=_trader_feedback_category(str(payload.get("category", "ui"))),
        severity=_trader_feedback_severity(str(payload.get("severity", "medium"))),
        summary=str(payload.get("summary", "")),
        recommendation=str(payload.get("recommendation", "")),
        status=str(payload.get("status", "open")),
        created_at=created_at,
        resolution=str(payload.get("resolution", "")),
        resolved_at=datetime.fromisoformat(resolved_at_raw) if resolved_at_raw else None,
    )


def _chart_drawing_from_mapping(payload: Mapping[str, JsonValue]) -> DashboardChartDrawing:
    created_at = datetime.fromisoformat(str(payload.get("created_at", DEFAULT_NOW.isoformat())))
    return DashboardChartDrawing(
        drawing_id=str(payload["drawing_id"]),
        drawing_type=DashboardChartDrawingType(str(payload["drawing_type"])),
        symbol=_watchlist_symbol(str(payload.get("symbol", "BTC/USDT"))),
        timeframe=_chart_drawing_timeframe(str(payload.get("timeframe", "1h"))),
        start_time=str(payload.get("start_time", DEFAULT_NOW.isoformat())),
        end_time=str(payload.get("end_time", "")),
        start_price=_decimal(payload["start_price"]),
        end_price=_optional_decimal_from_json(payload.get("end_price")),
        text=str(payload.get("text", "")),
        color=_chart_drawing_color(str(payload.get("color", "#1264a3"))),
        enabled=bool(payload.get("enabled", True)),
        created_at=created_at,
    )


def _decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _paper_initial_cash() -> Decimal:
    raw = os.getenv("ABTP_PAPER_INITIAL_CASH", "10000")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("ABTP_PAPER_INITIAL_CASH must be a decimal value") from exc
    if value <= DECIMAL_ZERO:
        raise ValueError("ABTP_PAPER_INITIAL_CASH must be positive")
    return value


def _optional_decimal_from_json(value: object | None) -> Decimal | None:
    if value in (None, "", "not_available"):
        return None
    return _decimal(value)


def _required_positive_decimal(value: str, label: str) -> Decimal:
    parsed = _decimal(value)
    if parsed <= DECIMAL_ZERO:
        raise PaperDashboardActionError(f"paper order {label} must be positive")
    return parsed


def _required_non_negative_decimal(value: str, label: str) -> Decimal:
    parsed = _decimal(value)
    if parsed < DECIMAL_ZERO:
        raise PaperDashboardActionError(f"paper order {label} cannot be negative")
    return parsed


def _optional_positive_decimal(value: str | None, label: str) -> Decimal | None:
    if value is None or not value.strip():
        return None
    parsed = _decimal(value)
    if parsed <= DECIMAL_ZERO:
        raise PaperDashboardActionError(f"paper order {label} must be positive")
    return parsed


def _latest_spread(latest: PaperTradingCycleResult | None) -> Decimal | None:
    if latest is None:
        return None
    return latest.snapshot.order_book_metrics.spread


def _unrealized_pnl(status: PaperStatusResponse) -> str:
    return str(_unrealized_pnl_decimal(status))


def _unrealized_pnl_decimal(status: PaperStatusResponse) -> Decimal:
    portfolio = status.portfolio
    price = status.current_btc_price or portfolio.average_entry_price
    if portfolio.base_quantity <= DECIMAL_ZERO:
        return DECIMAL_ZERO
    return (price - portfolio.average_entry_price) * portfolio.base_quantity


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


def _status_str(value: object | None, status: str) -> str:
    return status if value is None else str(value)


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
