"""Paper trading account state and accounting."""

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
class PaperAccountConfig:
    """Initial assumptions for simulated paper trading balances."""

    initial_cash: Decimal = Decimal("10000")
    quote_asset: Asset = Asset("USDT")
    base_asset: Asset = Asset("BTC")
    min_cash_reserve_pct: Decimal = Decimal("0.20")
    max_gross_exposure_pct: Decimal = Decimal("0.80")
    max_drawdown_pct: Decimal = Decimal("0.10")

    def __post_init__(self) -> None:
        if self.initial_cash <= Decimal("0"):
            raise ValueError("initial_cash must be positive")


@dataclass(frozen=True, slots=True)
class PaperTrade:
    """Simulated paper trade fill record."""

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
class PaperAccountState:
    """Current simulated paper account state."""

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


class PaperTradingAccount:
    """Apply simulated execution fills and expose portfolio risk context."""

    def __init__(self, config: PaperAccountConfig | None = None) -> None:
        self._config = config or PaperAccountConfig()
        self._state = PaperAccountState(
            cash=self._config.initial_cash,
            equity_history=(self._config.initial_cash,),
        )
        self._trades: list[PaperTrade] = []

    @property
    def config(self) -> PaperAccountConfig:
        return self._config

    @property
    def state(self) -> PaperAccountState:
        return self._state

    @property
    def trades(self) -> tuple[PaperTrade, ...]:
        return tuple(self._trades)

    def equity(self, price: Decimal) -> Decimal:
        """Return mark-to-market account equity."""

        if price <= Decimal("0"):
            raise ValueError("price must be positive")
        return self.state.cash + self.state.base_quantity * price

    def current_drawdown_pct(self, price: Decimal) -> Decimal:
        """Return current drawdown from observed paper equity history."""

        current = self.equity(price)
        peak = max((*self.state.equity_history, current))
        return (peak - current) / peak if peak > Decimal("0") else Decimal("0")

    def mark_to_market(self, price: Decimal) -> None:
        """Record an equity point without a simulated fill."""

        self._state = replace(
            self.state,
            equity_history=(*self.state.equity_history, self.equity(price)),
        )

    def risk_context(
        self,
        *,
        price: Decimal,
        checked_at: datetime,
        data_quality: DataQualityStatus | None = None,
    ) -> RiskPortfolioContext:
        """Build the Stage 022 portfolio context used by the risk engine."""

        manager = PortfolioManager(
            state=PortfolioManagerState(
                balances=(Balance(self._config.quote_asset, free=self.state.cash),),
                positions=self._positions(),
                prices={self._config.base_asset.symbol: price},
                equity_history=self.state.equity_history,
                data_quality=data_quality
                or DataQualityStatus(
                    trust_level=DataTrustLevel.TRUSTED,
                    issues=(),
                    source_ref="paper:account",
                    checked_at=checked_at,
                ),
            ),
            config=PortfolioManagerConfig(
                quote_asset=self._config.quote_asset,
                min_cash_reserve_pct=self._config.min_cash_reserve_pct,
                max_gross_exposure_pct=self._config.max_gross_exposure_pct,
                max_drawdown_pct=self._config.max_drawdown_pct,
                source_name="paper_trading_account",
            ),
        )
        return manager.risk_context(checked_at)

    def apply_execution(self, result: ExecutionResult, *, mark_price: Decimal) -> None:
        """Apply accepted paper-safe execution fills to simulated balances."""

        if not result.accepted or result.fill_summary is None:
            return
        cash = self.state.cash
        base_quantity = self.state.base_quantity
        average_entry = self.state.average_entry_price
        realized_pnl = self.state.realized_pnl
        fees_paid = self.state.fees_paid
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
                sold_quantity = min(fill.filled_quantity, base_quantity)
                cash += fill.notional - fill.fee_paid
                base_quantity -= sold_quantity
                realized_pnl += (fill.average_fill_price - average_entry) * sold_quantity
                if base_quantity == Decimal("0"):
                    average_entry = Decimal("0")
            fees_paid += fill.fee_paid
            self._trades.append(
                PaperTrade(
                    order_intent_id=result.intent.id,
                    side=result.intent.side,
                    quantity=fill.filled_quantity,
                    price=fill.average_fill_price,
                    fee_paid=fill.fee_paid,
                    occurred_at=fill.occurred_at,
                )
            )
        self._state = replace(
            self.state,
            cash=cash,
            base_quantity=base_quantity,
            average_entry_price=average_entry,
            realized_pnl=realized_pnl,
            fees_paid=fees_paid,
            equity_history=(*self.state.equity_history, cash + base_quantity * mark_price),
        )

    def _positions(self) -> tuple[PositionCostBasis, ...]:
        if self.state.base_quantity <= Decimal("0"):
            return ()
        return (
            PositionCostBasis(
                asset=self._config.base_asset,
                quantity=self.state.base_quantity,
                average_entry_price=max(self.state.average_entry_price, Decimal("0.01")),
                quote_asset=self._config.quote_asset,
            ),
        )
