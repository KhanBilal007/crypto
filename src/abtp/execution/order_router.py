"""Paper-safe order router."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.domain import OrderIntent, OrderSide, OrderStatus
from abtp.exchanges import (
    ExchangeAdapter,
    ExchangeAdapterError,
    ExchangeMode,
    UnsafeLiveOperationError,
)
from abtp.execution.fills import ExecutionFill
from abtp.risk import assert_order_intent_has_approved_risk


class OrderRouteMode(StrEnum):
    """Execution route mode."""

    PAPER = "paper"
    SANDBOX = "sandbox"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class OrderRouterConfig:
    """Paper-safe routing and fill assumptions."""

    mode: OrderRouteMode = OrderRouteMode.PAPER
    fee_bps: Decimal = Decimal("20")
    fill_ratio: Decimal = Decimal("1")
    price_adjustment_bps: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.mode is OrderRouteMode.LIVE:
            raise UnsafeLiveOperationError("live order route is unavailable in Stage 024")
        if self.fee_bps < Decimal("0") or self.price_adjustment_bps < Decimal("0"):
            raise ValueError("fee_bps and price_adjustment_bps cannot be negative")
        if not Decimal("0") <= self.fill_ratio <= Decimal("1"):
            raise ValueError("fill_ratio must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class OrderRouteRequest:
    """Router input for one risk-approved order intent."""

    intent: OrderIntent
    idempotency_key: str
    submitted_at: datetime
    execution_price: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        if self.execution_price is not None and self.execution_price <= Decimal("0"):
            raise ValueError("execution_price must be positive when supplied")


@dataclass(frozen=True, slots=True)
class OrderRouteResult:
    """Router output independent of exchange-specific APIs."""

    route_mode: OrderRouteMode
    exchange_order_id: str | None
    status: OrderStatus
    submitted_at: datetime
    fills: tuple[ExecutionFill, ...]
    reason: str | None = None

    @property
    def filled_quantity(self) -> Decimal:
        return sum((fill.filled_quantity for fill in self.fills), Decimal("0"))


class PaperOrderRouter:
    """Route orders to deterministic paper fills or sandbox adapters only."""

    def __init__(
        self,
        *,
        config: OrderRouterConfig | None = None,
        adapter: ExchangeAdapter | None = None,
    ) -> None:
        self._config = config or OrderRouterConfig()
        self._adapter = adapter
        if adapter is not None and adapter.mode is ExchangeMode.LIVE:
            raise UnsafeLiveOperationError("live adapters are unavailable in Stage 024")

    @property
    def config(self) -> OrderRouterConfig:
        return self._config

    def route(self, request: OrderRouteRequest) -> OrderRouteResult:
        """Route a risk-approved order intent in paper-safe mode."""

        assert_order_intent_has_approved_risk(request.intent)
        if self._adapter is not None:
            return self._route_adapter(request)
        return self._route_paper(request)

    def _route_adapter(self, request: OrderRouteRequest) -> OrderRouteResult:
        adapter = self._adapter
        if adapter is None:
            raise RuntimeError("adapter route requires an adapter")
        try:
            exchange_order = adapter.submit_order(request.intent)
        except ExchangeAdapterError as exc:
            return OrderRouteResult(
                route_mode=OrderRouteMode.SANDBOX,
                exchange_order_id=None,
                status=OrderStatus.FAILED,
                submitted_at=request.submitted_at,
                fills=(),
                reason=str(exc),
            )
        fill = ExecutionFill(
            order_intent_id=request.intent.id,
            exchange_order_id=exchange_order.exchange_order_id,
            filled_quantity=exchange_order.filled_quantity,
            average_fill_price=exchange_order.average_fill_price or Decimal("0"),
            fee_paid=exchange_order.fee_paid,
            occurred_at=exchange_order.submitted_at,
            liquidity="sandbox",
        )
        return OrderRouteResult(
            route_mode=OrderRouteMode.SANDBOX,
            exchange_order_id=exchange_order.exchange_order_id,
            status=exchange_order.status,
            submitted_at=exchange_order.submitted_at,
            fills=(fill,),
            reason=exchange_order.reason,
        )

    def _route_paper(self, request: OrderRouteRequest) -> OrderRouteResult:
        price = request.execution_price or request.intent.limit_price
        if price is None:
            return OrderRouteResult(
                route_mode=OrderRouteMode.PAPER,
                exchange_order_id=None,
                status=OrderStatus.FAILED,
                submitted_at=request.submitted_at,
                fills=(),
                reason="paper route requires execution_price for market orders",
            )
        direction = Decimal("1") if request.intent.side is OrderSide.BUY else Decimal("-1")
        adjusted_price = price * (
            Decimal("1") + direction * self.config.price_adjustment_bps / Decimal("10000")
        )
        filled_quantity = request.intent.quantity * self.config.fill_ratio
        exchange_order_id = f"paper-{request.intent.id}"
        fills = (
            (
                ExecutionFill(
                    order_intent_id=request.intent.id,
                    exchange_order_id=exchange_order_id,
                    filled_quantity=filled_quantity,
                    average_fill_price=adjusted_price,
                    fee_paid=(
                        filled_quantity * adjusted_price * self.config.fee_bps / Decimal("10000")
                    ),
                    occurred_at=request.submitted_at,
                ),
            )
            if filled_quantity > Decimal("0")
            else ()
        )
        status = (
            OrderStatus.FILLED
            if filled_quantity >= request.intent.quantity
            else OrderStatus.SUBMITTED
        )
        return OrderRouteResult(
            route_mode=OrderRouteMode.PAPER,
            exchange_order_id=exchange_order_id,
            status=status,
            submitted_at=request.submitted_at,
            fills=fills,
            reason="partial paper fill" if status is OrderStatus.SUBMITTED else None,
        )
