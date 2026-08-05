"""Order-book metrics and delta utilities."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from abtp.domain import OrderBookLevel, OrderBookSnapshot


@dataclass(frozen=True, slots=True)
class OrderBookMetrics:
    """Derived order-book values for data-quality and future risk modules."""

    best_bid: Decimal
    best_ask: Decimal
    spread: Decimal
    bid_depth: Decimal
    ask_depth: Decimal
    imbalance: Decimal


@dataclass(frozen=True, slots=True)
class OrderBookDelta:
    """Simple snapshot-to-snapshot order-book diff."""

    changed_bids: tuple[OrderBookLevel, ...]
    changed_asks: tuple[OrderBookLevel, ...]
    removed_bid_prices: tuple[Decimal, ...]
    removed_ask_prices: tuple[Decimal, ...]


def calculate_order_book_metrics(snapshot: OrderBookSnapshot) -> OrderBookMetrics:
    """Calculate spread, depth, and imbalance from a snapshot."""

    best_bid = max(level.price for level in snapshot.bids)
    best_ask = min(level.price for level in snapshot.asks)
    bid_depth = sum((level.quantity for level in snapshot.bids), start=Decimal("0"))
    ask_depth = sum((level.quantity for level in snapshot.asks), start=Decimal("0"))
    total_depth = bid_depth + ask_depth
    imbalance = (
        Decimal("0") if total_depth == Decimal("0") else (bid_depth - ask_depth) / total_depth
    )
    return OrderBookMetrics(
        best_bid=best_bid,
        best_ask=best_ask,
        spread=best_ask - best_bid,
        bid_depth=bid_depth,
        ask_depth=ask_depth,
        imbalance=imbalance,
    )


def diff_order_books(previous: OrderBookSnapshot, current: OrderBookSnapshot) -> OrderBookDelta:
    """Return changed levels and removed prices between snapshots."""

    if previous.pair != current.pair:
        raise ValueError("cannot diff order books for different pairs")
    previous_bids = {level.price: level.quantity for level in previous.bids}
    previous_asks = {level.price: level.quantity for level in previous.asks}
    current_bids = {level.price: level.quantity for level in current.bids}
    current_asks = {level.price: level.quantity for level in current.asks}
    return OrderBookDelta(
        changed_bids=tuple(
            level for level in current.bids if previous_bids.get(level.price) != level.quantity
        ),
        changed_asks=tuple(
            level for level in current.asks if previous_asks.get(level.price) != level.quantity
        ),
        removed_bid_prices=tuple(price for price in previous_bids if price not in current_bids),
        removed_ask_prices=tuple(price for price in previous_asks if price not in current_asks),
    )
