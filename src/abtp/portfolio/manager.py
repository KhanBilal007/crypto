"""Portfolio and position manager."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from abtp.data import DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain import Asset, PortfolioPosition, PortfolioSnapshot
from abtp.portfolio.accounting import (
    Balance,
    OpenOrderReservation,
    PositionCostBasis,
    calculate_drawdown,
)
from abtp.portfolio.exposure import (
    ExposureSummary,
    aggregate_exposure,
    drawdown_limit_breached,
    exposure_limit_breached,
    has_min_cash_reserve,
)
from abtp.risk import RiskPortfolioContext


@dataclass(frozen=True, slots=True)
class PortfolioManagerConfig:
    """Portfolio constraints consumed by the manager and risk engine."""

    quote_asset: Asset = Asset("USDT")
    min_cash_reserve_pct: Decimal = Decimal("0.20")
    max_gross_exposure_pct: Decimal = Decimal("0.80")
    max_drawdown_pct: Decimal = Decimal("0.10")
    source_name: str = "portfolio_manager"

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.min_cash_reserve_pct, "min_cash_reserve_pct"),
            (self.max_gross_exposure_pct, "max_gross_exposure_pct"),
            (self.max_drawdown_pct, "max_drawdown_pct"),
        ):
            if not Decimal("0") <= value <= Decimal("1"):
                raise ValueError(f"{field_name} must be between 0 and 1")
        if not self.source_name.strip():
            raise ValueError("source_name is required")


@dataclass(frozen=True, slots=True)
class PortfolioManagerState:
    """Deterministic local state for portfolio snapshots."""

    balances: tuple[Balance, ...]
    positions: tuple[PositionCostBasis, ...]
    prices: Mapping[str, Decimal]
    equity_history: tuple[Decimal, ...] = ()
    open_order_reservations: tuple[OpenOrderReservation, ...] = ()
    data_quality: DataQualityStatus | None = None

    def __post_init__(self) -> None:
        if not self.balances:
            raise ValueError("at least one balance is required")
        for symbol, price in self.prices.items():
            if not symbol.strip():
                raise ValueError("price symbol is required")
            if price <= Decimal("0"):
                raise ValueError("prices must be positive")


@dataclass(frozen=True, slots=True)
class PortfolioConstraintStatus:
    """Portfolio-level ability to open new positions."""

    can_open_new_positions: bool
    reasons: tuple[str, ...]
    cash_reserve_pct: Decimal
    gross_exposure_pct: Decimal
    current_drawdown_pct: Decimal


class PortfolioManager:
    """Build consistent portfolio snapshots and risk context from local state."""

    def __init__(
        self,
        *,
        state: PortfolioManagerState,
        config: PortfolioManagerConfig | None = None,
    ) -> None:
        self._state = state
        self._config = config or PortfolioManagerConfig()

    @property
    def config(self) -> PortfolioManagerConfig:
        return self._config

    @property
    def state(self) -> PortfolioManagerState:
        return self._state

    def snapshot(self, captured_at: datetime | None = None) -> PortfolioSnapshot:
        """Return a domain snapshot suitable for persistence and risk review."""

        checked_at = normalize_timestamp(captured_at or datetime.now(UTC))
        positions = tuple(self._domain_position(position) for position in self.state.positions)
        return PortfolioSnapshot(
            captured_at=checked_at,
            positions=positions,
            source_ref=f"{self.config.source_name}:{checked_at.isoformat()}",
        )

    def risk_context(self, captured_at: datetime | None = None) -> RiskPortfolioContext:
        """Return Stage 022 risk context for pre-decision checks."""

        snapshot = self.snapshot(captured_at)
        total_equity = self.total_equity()
        available_cash = self.available_cash()
        exposure = aggregate_exposure(snapshot.positions, total_equity=total_equity)
        return RiskPortfolioContext(
            total_equity=total_equity,
            available_cash=available_cash,
            current_exposure=exposure.gross_exposure,
            correlated_exposure=Decimal("0"),
            current_drawdown_pct=self.current_drawdown_pct(),
            daily_pnl=self._period_pnl(1),
            weekly_pnl=self._period_pnl(7),
            data_quality=self._quality(captured_at),
        )

    def exposure_summary(self, captured_at: datetime | None = None) -> ExposureSummary:
        """Return aggregate exposure for the current snapshot."""

        snapshot = self.snapshot(captured_at)
        return aggregate_exposure(snapshot.positions, total_equity=self.total_equity())

    def constraints(self, captured_at: datetime | None = None) -> PortfolioConstraintStatus:
        """Evaluate cash reserve, exposure, and drawdown constraints."""

        total_equity = self.total_equity()
        available_cash = self.available_cash()
        exposure = self.exposure_summary(captured_at)
        drawdown = self.current_drawdown_pct()
        reasons: list[str] = []
        if not has_min_cash_reserve(
            available_cash=available_cash,
            total_equity=total_equity,
            min_cash_reserve_pct=self.config.min_cash_reserve_pct,
        ):
            reasons.append("minimum cash reserve is breached")
        if exposure_limit_breached(
            exposure,
            max_gross_exposure_pct=self.config.max_gross_exposure_pct,
        ):
            reasons.append("gross exposure limit is breached")
        if drawdown_limit_breached(
            current_drawdown_pct=drawdown,
            max_drawdown_pct=self.config.max_drawdown_pct,
        ):
            reasons.append("drawdown limit is breached")
        return PortfolioConstraintStatus(
            can_open_new_positions=not reasons,
            reasons=tuple(reasons),
            cash_reserve_pct=available_cash / total_equity,
            gross_exposure_pct=exposure.gross_exposure_pct,
            current_drawdown_pct=drawdown,
        )

    def total_equity(self) -> Decimal:
        """Return quote-denominated equity from cash and open positions."""

        quote_cash = sum(
            (
                balance.total
                for balance in self.state.balances
                if balance.asset == self.config.quote_asset
            ),
            Decimal("0"),
        )
        position_value = sum(
            (self._position_market_value(position) for position in self.state.positions),
            Decimal("0"),
        )
        return quote_cash + position_value

    def available_cash(self) -> Decimal:
        """Return free quote cash minus open-order reservations."""

        quote_free = sum(
            (
                balance.free
                for balance in self.state.balances
                if balance.asset == self.config.quote_asset
            ),
            Decimal("0"),
        )
        reserved = sum(
            (
                reservation.reserved_cash
                for reservation in self.state.open_order_reservations
                if reservation.quote_asset == self.config.quote_asset
            ),
            Decimal("0"),
        )
        return max(Decimal("0"), quote_free - reserved)

    def current_drawdown_pct(self) -> Decimal:
        """Return max drawdown over supplied history including current equity."""

        history = (*self.state.equity_history, self.total_equity())
        return calculate_drawdown(history)

    def _domain_position(self, position: PositionCostBasis) -> PortfolioPosition:
        return PortfolioPosition(
            asset=position.asset,
            quantity=position.quantity,
            valuation_quote=self.config.quote_asset,
            valuation=self._position_market_value(position),
        )

    def _position_market_value(self, position: PositionCostBasis) -> Decimal:
        price = self.state.prices.get(position.asset.symbol)
        if price is None:
            raise ValueError(f"missing price for position asset: {position.asset.symbol}")
        return position.quantity * price

    def _period_pnl(self, periods: int) -> Decimal:
        if len(self.state.equity_history) <= periods:
            return Decimal("0")
        return self.total_equity() - self.state.equity_history[-periods]

    def _quality(self, captured_at: datetime | None) -> DataQualityStatus:
        if self.state.data_quality is not None:
            return self.state.data_quality
        checked_at = normalize_timestamp(captured_at or datetime.now(UTC))
        return DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref="portfolio_manager",
            checked_at=checked_at,
        )
