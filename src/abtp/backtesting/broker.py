"""Deterministic backtest broker/accounting."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from abtp.data import DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, OrderSide
from abtp.execution import ExecutionResult
from abtp.portfolio import Balance, PortfolioManager, PortfolioManagerConfig, PortfolioManagerState
from abtp.portfolio.accounting import PositionCostBasis
from abtp.risk import RiskPortfolioContext


@dataclass(frozen=True, slots=True)
class BacktestBrokerConfig:
    """Initial account assumptions for deterministic backtests."""

    initial_cash: Decimal
    quote_asset: Asset = Asset("USDT")
    base_asset: Asset = Asset("BTC")
    min_cash_reserve_pct: Decimal = Decimal("0.20")
    max_gross_exposure_pct: Decimal = Decimal("0.80")
    max_drawdown_pct: Decimal = Decimal("0.10")

    def __post_init__(self) -> None:
        if self.initial_cash <= Decimal("0"):
            raise ValueError("initial_cash must be positive")


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    """Executed trade record from simulated execution."""

    order_intent_id: UUID
    side: OrderSide
    quantity: Decimal
    price: Decimal
    fee_paid: Decimal
    occurred_at: datetime

    @property
    def notional(self) -> Decimal:
        return self.quantity * self.price


@dataclass(frozen=True, slots=True)
class BacktestAccount:
    """Backtest cash/position state."""

    cash: Decimal
    base_quantity: Decimal = Decimal("0")
    average_entry_price: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    fees_paid: Decimal = Decimal("0")
    equity_history: tuple[Decimal, ...] = ()

    def __post_init__(self) -> None:
        if self.cash < Decimal("0"):
            raise ValueError("cash cannot be negative")
        if self.base_quantity < Decimal("0"):
            raise ValueError("base_quantity cannot be negative")
        if self.average_entry_price < Decimal("0"):
            raise ValueError("average_entry_price cannot be negative")


class BacktestBroker:
    """Apply paper execution fills and expose risk-ready portfolio state."""

    def __init__(self, config: BacktestBrokerConfig) -> None:
        self._config = config
        self._account = BacktestAccount(
            cash=config.initial_cash,
            equity_history=(config.initial_cash,),
        )
        self._trades: list[BacktestTrade] = []

    @property
    def account(self) -> BacktestAccount:
        return self._account

    @property
    def trades(self) -> tuple[BacktestTrade, ...]:
        return tuple(self._trades)

    def equity(self, price: Decimal) -> Decimal:
        """Return current mark-to-market equity."""

        if price <= Decimal("0"):
            raise ValueError("price must be positive")
        return self.account.cash + self.account.base_quantity * price

    def current_drawdown_pct(self, price: Decimal) -> Decimal:
        """Return drawdown from broker equity history and current price."""

        current = self.equity(price)
        peak = max((*self.account.equity_history, current))
        return (peak - current) / peak if peak > Decimal("0") else Decimal("0")

    def risk_context(self, *, price: Decimal, checked_at: datetime) -> RiskPortfolioContext:
        """Build Stage 022 risk context from current account state."""

        manager = PortfolioManager(
            state=PortfolioManagerState(
                balances=(Balance(self._config.quote_asset, free=self.account.cash),),
                positions=self._positions(),
                prices={self._config.base_asset.symbol: price},
                equity_history=self.account.equity_history,
                data_quality=DataQualityStatus(
                    trust_level=DataTrustLevel.TRUSTED,
                    issues=(),
                    source_ref="backtest:broker",
                    checked_at=checked_at,
                ),
            ),
            config=PortfolioManagerConfig(
                quote_asset=self._config.quote_asset,
                min_cash_reserve_pct=self._config.min_cash_reserve_pct,
                max_gross_exposure_pct=self._config.max_gross_exposure_pct,
                max_drawdown_pct=self._config.max_drawdown_pct,
                source_name="backtest_broker",
            ),
        )
        return manager.risk_context(checked_at)

    def apply_execution(self, result: ExecutionResult, *, mark_price: Decimal) -> None:
        """Apply accepted execution fills to local account state."""

        if not result.accepted or result.fill_summary is None:
            return
        cash = self.account.cash
        base_quantity = self.account.base_quantity
        average_entry = self.account.average_entry_price
        fees_paid = self.account.fees_paid
        for fill in result.route_result.fills if result.route_result is not None else ():
            if result.intent.side is OrderSide.BUY:
                total_cost = fill.notional + fill.fee_paid
                cash -= total_cost
                previous_cost = base_quantity * average_entry
                base_quantity += fill.filled_quantity
                average_entry = (
                    (previous_cost + fill.notional) / base_quantity
                    if base_quantity > Decimal("0")
                    else Decimal("0")
                )
            else:
                cash += fill.notional - fill.fee_paid
                base_quantity -= fill.filled_quantity
            fees_paid += fill.fee_paid
            self._trades.append(
                BacktestTrade(
                    order_intent_id=result.intent.id,
                    side=result.intent.side,
                    quantity=fill.filled_quantity,
                    price=fill.average_fill_price,
                    fee_paid=fill.fee_paid,
                    occurred_at=fill.occurred_at,
                )
            )
        equity_history = (*self.account.equity_history, cash + base_quantity * mark_price)
        self._account = replace(
            self.account,
            cash=cash,
            base_quantity=base_quantity,
            average_entry_price=average_entry,
            fees_paid=fees_paid,
            equity_history=equity_history,
        )

    def mark_to_market(self, price: Decimal) -> None:
        """Record an equity point without executing a trade."""

        self._account = replace(
            self.account,
            equity_history=(*self.account.equity_history, self.equity(price)),
        )

    def _positions(self) -> tuple[PositionCostBasis, ...]:
        if self.account.base_quantity <= Decimal("0"):
            return ()
        return (
            PositionCostBasis(
                asset=self._config.base_asset,
                quantity=self.account.base_quantity,
                average_entry_price=max(self.account.average_entry_price, Decimal("0.01")),
                quote_asset=self._config.quote_asset,
            ),
        )
