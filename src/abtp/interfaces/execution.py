"""Execution module interfaces."""

from __future__ import annotations

from typing import Protocol

from abtp.domain.enums import OrderStatus
from abtp.domain.models import OrderIntent, RiskDecision


class OrderExecutionGateway(Protocol):
    """Future execution contract.

    Implementations must accept only risk-approved order intents. Actual
    exchange calls belong in exchange adapter modules introduced by later stages.
    """

    def submit(self, intent: OrderIntent, risk_decision: RiskDecision) -> OrderStatus:
        """Submit an approved order intent to a future execution adapter."""
        ...
