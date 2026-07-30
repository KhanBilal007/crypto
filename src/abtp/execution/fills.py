"""Fill records and summary helpers for paper-safe execution."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ExecutionFill:
    """One simulated or adapter-reported fill."""

    order_intent_id: UUID
    exchange_order_id: str
    filled_quantity: Decimal
    average_fill_price: Decimal
    fee_paid: Decimal
    occurred_at: datetime
    liquidity: str = "paper"

    def __post_init__(self) -> None:
        if not self.exchange_order_id.strip():
            raise ValueError("exchange_order_id is required")
        if self.filled_quantity < Decimal("0"):
            raise ValueError("filled_quantity cannot be negative")
        if self.average_fill_price <= Decimal("0"):
            raise ValueError("average_fill_price must be positive")
        if self.fee_paid < Decimal("0"):
            raise ValueError("fee_paid cannot be negative")
        if not self.liquidity.strip():
            raise ValueError("liquidity is required")

    @property
    def notional(self) -> Decimal:
        return self.filled_quantity * self.average_fill_price


@dataclass(frozen=True, slots=True)
class FillSummary:
    """Aggregated fill state for one order intent."""

    requested_quantity: Decimal
    filled_quantity: Decimal
    average_fill_price: Decimal | None
    fee_paid: Decimal
    is_complete: bool
    is_partial: bool


def build_fill_summary(
    fills: Sequence[ExecutionFill],
    *,
    requested_quantity: Decimal,
) -> FillSummary:
    """Summarize fills without requiring exchange-specific payloads."""

    if requested_quantity <= Decimal("0"):
        raise ValueError("requested_quantity must be positive")
    filled_quantity = sum((fill.filled_quantity for fill in fills), Decimal("0"))
    fee_paid = sum((fill.fee_paid for fill in fills), Decimal("0"))
    notional = sum((fill.notional for fill in fills), Decimal("0"))
    average_price = notional / filled_quantity if filled_quantity > Decimal("0") else None
    return FillSummary(
        requested_quantity=requested_quantity,
        filled_quantity=filled_quantity,
        average_fill_price=average_price,
        fee_paid=fee_paid,
        is_complete=filled_quantity >= requested_quantity,
        is_partial=Decimal("0") < filled_quantity < requested_quantity,
    )
