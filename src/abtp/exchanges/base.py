"""Base exchange adapter contracts.

Only exchange adapter modules may contain exchange-specific API behavior. Stage
009 defines contracts and sandbox behavior only; it does not implement real
HTTP or websocket calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from abtp.domain import Asset, AssetPair, Candle, OrderBookSnapshot, OrderIntent, OrderStatus


class ExchangeMode(StrEnum):
    """Exchange adapter operating modes."""

    SANDBOX = "sandbox"
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class ExchangeSymbol:
    """Symbol metadata used for adapter validation."""

    pair: AssetPair
    tick_size: Decimal
    lot_size: Decimal
    min_order_size: Decimal
    maker_fee_bps: Decimal
    taker_fee_bps: Decimal
    supports_margin: bool = False
    supports_futures: bool = False
    supports_withdrawals: bool = False

    def __post_init__(self) -> None:
        if self.tick_size <= Decimal("0"):
            raise ValueError("tick_size must be positive")
        if self.lot_size <= Decimal("0"):
            raise ValueError("lot_size must be positive")
        if self.min_order_size <= Decimal("0"):
            raise ValueError("min_order_size must be positive")
        if self.supports_margin or self.supports_futures or self.supports_withdrawals:
            raise ValueError("non-spot exchange capabilities are disabled in Stage 009")


@dataclass(frozen=True, slots=True)
class Balance:
    """Available and held quantity for one asset."""

    asset: Asset
    available: Decimal
    held: Decimal = Decimal("0")

    @property
    def total(self) -> Decimal:
        return self.available + self.held


@dataclass(frozen=True, slots=True)
class Ticker:
    """Deterministic ticker snapshot."""

    pair: AssetPair
    price: Decimal
    captured_at: datetime
    source_ref: str


@dataclass(frozen=True, slots=True)
class RateLimitState:
    """Adapter rate-limit state for observability."""

    limit: int
    remaining: int
    reset_at: datetime


@dataclass(frozen=True, slots=True)
class ExchangeOrder:
    """Exchange-facing order lifecycle result."""

    exchange_order_id: str
    intent: OrderIntent
    status: OrderStatus
    submitted_at: datetime
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Decimal | None = None
    fee_paid: Decimal = Decimal("0")
    reason: str | None = None


class ExchangeAdapter(Protocol):
    """Unified exchange adapter contract for future data/execution modules."""

    @property
    def name(self) -> str:
        """Exchange adapter name."""
        ...

    @property
    def mode(self) -> ExchangeMode:
        """Adapter mode."""
        ...

    def symbols(self) -> tuple[ExchangeSymbol, ...]:
        """Return supported spot symbols."""
        ...

    def balances(self) -> tuple[Balance, ...]:
        """Return account balances for sandbox/paper/live adapter state."""
        ...

    def ticker(self, pair: AssetPair) -> Ticker:
        """Return a ticker snapshot."""
        ...

    def candles(self, pair: AssetPair, interval: str, limit: int) -> tuple[Candle, ...]:
        """Return recent candles."""
        ...

    def order_book(self, pair: AssetPair) -> OrderBookSnapshot:
        """Return an order book snapshot."""
        ...

    def submit_order(self, intent: OrderIntent) -> ExchangeOrder:
        """Submit a risk-approved order intent."""
        ...

    def get_order(self, exchange_order_id: str) -> ExchangeOrder:
        """Return an order lifecycle result."""
        ...

    def cancel_order(self, exchange_order_id: str) -> ExchangeOrder:
        """Cancel an open order when supported."""
        ...

    def rate_limit_state(self) -> RateLimitState:
        """Return current rate-limit state."""
        ...
