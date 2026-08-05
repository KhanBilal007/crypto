"""Portfolio module interfaces."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from abtp.domain.models import PortfolioSnapshot


class PortfolioRepository(Protocol):
    """Portfolio state access contract."""

    def snapshot(self, captured_at: datetime | None = None) -> PortfolioSnapshot:
        """Return a portfolio snapshot suitable for risk evaluation."""
        ...
