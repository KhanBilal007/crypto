"""Deterministic portfolio accounting helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from abtp.domain import Asset


@dataclass(frozen=True, slots=True)
class Balance:
    """Free and reserved asset balance."""

    asset: Asset
    free: Decimal
    reserved: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.free < Decimal("0") or self.reserved < Decimal("0"):
            raise ValueError("balance free/reserved cannot be negative")

    @property
    def total(self) -> Decimal:
        return self.free + self.reserved


@dataclass(frozen=True, slots=True)
class PositionCostBasis:
    """Spot position quantity and average entry price."""

    asset: Asset
    quantity: Decimal
    average_entry_price: Decimal
    quote_asset: Asset

    def __post_init__(self) -> None:
        if self.quantity < Decimal("0"):
            raise ValueError("position quantity cannot be negative")
        if self.average_entry_price <= Decimal("0"):
            raise ValueError("average_entry_price must be positive")


@dataclass(frozen=True, slots=True)
class UnrealizedPnL:
    """Unrealized P/L for one open position."""

    asset: Asset
    quantity: Decimal
    cost_basis: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal


@dataclass(frozen=True, slots=True)
class RealizedPnL:
    """Realized P/L from a closed quantity after fees."""

    asset: Asset
    quantity: Decimal
    gross_pnl: Decimal
    fees_paid: Decimal
    net_pnl: Decimal


@dataclass(frozen=True, slots=True)
class OpenOrderReservation:
    """Cash reserved for an open order plus fee buffer."""

    order_ref: str
    quote_asset: Asset
    order_notional: Decimal
    fee_buffer: Decimal

    def __post_init__(self) -> None:
        if not self.order_ref.strip():
            raise ValueError("order_ref is required")
        if self.order_notional <= Decimal("0"):
            raise ValueError("order_notional must be positive")
        if self.fee_buffer < Decimal("0"):
            raise ValueError("fee_buffer cannot be negative")

    @property
    def reserved_cash(self) -> Decimal:
        return self.order_notional + self.fee_buffer


def calculate_unrealized_pnl(
    position: PositionCostBasis,
    *,
    market_price: Decimal,
) -> UnrealizedPnL:
    """Calculate unrealized P/L for an open spot position."""

    if market_price <= Decimal("0"):
        raise ValueError("market_price must be positive")
    cost_basis = position.quantity * position.average_entry_price
    market_value = position.quantity * market_price
    pnl = market_value - cost_basis
    pct = pnl / cost_basis if cost_basis > Decimal("0") else Decimal("0")
    return UnrealizedPnL(
        asset=position.asset,
        quantity=position.quantity,
        cost_basis=cost_basis,
        market_value=market_value,
        unrealized_pnl=pnl,
        unrealized_pnl_pct=pct,
    )


def calculate_realized_pnl(
    *,
    asset: Asset,
    quantity: Decimal,
    entry_price: Decimal,
    exit_price: Decimal,
    fee_bps: Decimal,
) -> RealizedPnL:
    """Calculate realized P/L for a deterministic fill pair."""

    for value, field_name in (
        (quantity, "quantity"),
        (entry_price, "entry_price"),
        (exit_price, "exit_price"),
    ):
        if value <= Decimal("0"):
            raise ValueError(f"{field_name} must be positive")
    if fee_bps < Decimal("0"):
        raise ValueError("fee_bps cannot be negative")
    gross = quantity * (exit_price - entry_price)
    fees = quantity * (entry_price + exit_price) * fee_bps / Decimal("10000")
    return RealizedPnL(
        asset=asset,
        quantity=quantity,
        gross_pnl=gross,
        fees_paid=fees,
        net_pnl=gross - fees,
    )


def calculate_drawdown(equity_values: Sequence[Decimal]) -> Decimal:
    """Return maximum drawdown percentage from an equity curve."""

    if not equity_values:
        return Decimal("0")
    peak = equity_values[0]
    max_drawdown = Decimal("0")
    for value in equity_values:
        if value <= Decimal("0"):
            raise ValueError("equity values must be positive")
        peak = max(peak, value)
        drawdown = (peak - value) / peak
        max_drawdown = max(max_drawdown, drawdown)
    return max_drawdown


def reserve_open_order_cash(
    *,
    available_cash: Decimal,
    quote_asset: Asset,
    order_notional: Decimal,
    fee_bps: Decimal,
    order_ref: str,
) -> OpenOrderReservation:
    """Reserve cash for an open order without placing the order."""

    if available_cash < Decimal("0"):
        raise ValueError("available_cash cannot be negative")
    if fee_bps < Decimal("0"):
        raise ValueError("fee_bps cannot be negative")
    fee_buffer = order_notional * fee_bps / Decimal("10000")
    reservation = OpenOrderReservation(
        order_ref=order_ref,
        quote_asset=quote_asset,
        order_notional=order_notional,
        fee_buffer=fee_buffer,
    )
    if reservation.reserved_cash > available_cash:
        raise ValueError("insufficient available cash for open-order reservation")
    return reservation
