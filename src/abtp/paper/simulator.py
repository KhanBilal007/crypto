"""Deterministic paper fill simulation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from abtp.domain import OrderSide
from abtp.execution import OrderRouteMode, OrderRouterConfig, PaperOrderRouter


@dataclass(frozen=True, slots=True)
class PaperFillSimulationConfig:
    """Paper fill assumptions for live-like simulated execution."""

    fee_bps: Decimal = Decimal("20")
    spread_bps: Decimal = Decimal("10")
    slippage_bps: Decimal = Decimal("5")
    fill_ratio: Decimal = Decimal("1")
    latency_ms: int = 50

    def __post_init__(self) -> None:
        if self.fee_bps < Decimal("0"):
            raise ValueError("fee_bps cannot be negative")
        if self.spread_bps < Decimal("0") or self.slippage_bps < Decimal("0"):
            raise ValueError("spread_bps and slippage_bps cannot be negative")
        if not Decimal("0") <= self.fill_ratio <= Decimal("1"):
            raise ValueError("fill_ratio must be between 0 and 1")
        if self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")

    @property
    def price_adjustment_bps(self) -> Decimal:
        """Return half-spread plus slippage cost in basis points."""

        return self.spread_bps / Decimal("2") + self.slippage_bps


@dataclass(frozen=True, slots=True)
class SimulatedFillEstimate:
    """Pre-order live-like fill estimate for audit and risk checks."""

    reference_price: Decimal
    side: OrderSide
    execution_price: Decimal
    fee_bps: Decimal
    spread_bps: Decimal
    slippage_bps: Decimal
    fill_ratio: Decimal
    latency_ms: int


def estimate_paper_fill(
    *,
    reference_price: Decimal,
    side: OrderSide,
    config: PaperFillSimulationConfig | None = None,
) -> SimulatedFillEstimate:
    """Estimate a deterministic paper fill price from top-of-book assumptions."""

    active_config = config or PaperFillSimulationConfig()
    if reference_price <= Decimal("0"):
        raise ValueError("reference_price must be positive")
    direction = Decimal("1") if side is OrderSide.BUY else Decimal("-1")
    execution_price = reference_price * (
        Decimal("1") + direction * active_config.price_adjustment_bps / Decimal("10000")
    )
    return SimulatedFillEstimate(
        reference_price=reference_price,
        side=side,
        execution_price=execution_price,
        fee_bps=active_config.fee_bps,
        spread_bps=active_config.spread_bps,
        slippage_bps=active_config.slippage_bps,
        fill_ratio=active_config.fill_ratio,
        latency_ms=active_config.latency_ms,
    )


def build_paper_order_router(
    config: PaperFillSimulationConfig | None = None,
) -> PaperOrderRouter:
    """Build a Stage 024 paper router, never a live route."""

    active_config = config or PaperFillSimulationConfig()
    return PaperOrderRouter(
        config=OrderRouterConfig(
            mode=OrderRouteMode.PAPER,
            fee_bps=active_config.fee_bps,
            fill_ratio=active_config.fill_ratio,
            price_adjustment_bps=active_config.price_adjustment_bps,
        )
    )
