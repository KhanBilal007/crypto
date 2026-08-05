"""Data module interfaces.

Exchange API calls belong in future exchange adapter modules, not in these
interfaces or their tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from abtp.domain.models import AssetPair, Candle, OrderBookSnapshot, Trade


class MarketDataProvider(Protocol):
    """Read-only market data provider contract."""

    def candles(
        self, pair: AssetPair, interval: str, start: datetime, end: datetime
    ) -> tuple[Candle, ...]:
        """Return deterministic candle data for the requested range."""
        ...

    def order_book(self, pair: AssetPair) -> OrderBookSnapshot:
        """Return the latest available order book snapshot."""
        ...

    def trades(self, pair: AssetPair, start: datetime, end: datetime) -> tuple[Trade, ...]:
        """Return observed trades for the requested range."""
        ...
