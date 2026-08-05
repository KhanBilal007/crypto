"""Risk module interfaces."""

from __future__ import annotations

from typing import Protocol

from abtp.domain.models import OrderIntent, PortfolioSnapshot, RiskDecision


class RiskManagementEngine(Protocol):
    """Required risk gate for every order path."""

    def evaluate(self, intent: OrderIntent, portfolio: PortfolioSnapshot) -> RiskDecision:
        """Evaluate an order intent before it can be submitted."""
        ...
