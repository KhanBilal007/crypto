"""Deterministic fee and slippage model for backtests."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from abtp.domain import OrderSide


@dataclass(frozen=True, slots=True)
class SlippageModelConfig:
    """Cost assumptions used by historical simulation."""

    fee_bps: Decimal = Decimal("20")
    spread_bps: Decimal = Decimal("10")
    slippage_bps: Decimal = Decimal("5")

    def __post_init__(self) -> None:
        if self.fee_bps < Decimal("0"):
            raise ValueError("fee_bps cannot be negative")
        if self.spread_bps < Decimal("0") or self.slippage_bps < Decimal("0"):
            raise ValueError("spread_bps and slippage_bps cannot be negative")


def estimate_execution_price(
    *,
    reference_price: Decimal,
    side: OrderSide,
    config: SlippageModelConfig,
) -> Decimal:
    """Return deterministic execution price including half-spread and slippage."""

    if reference_price <= Decimal("0"):
        raise ValueError("reference_price must be positive")
    adjustment_bps = config.slippage_bps + config.spread_bps / Decimal("2")
    adjustment = reference_price * adjustment_bps / Decimal("10000")
    if side is OrderSide.BUY:
        return reference_price + adjustment
    return reference_price - adjustment


def total_cost_bps(config: SlippageModelConfig) -> Decimal:
    """Return explicit total assumed cost in basis points."""

    return config.fee_bps + config.spread_bps / Decimal("2") + config.slippage_bps
