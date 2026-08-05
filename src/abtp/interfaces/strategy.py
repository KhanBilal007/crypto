"""Strategy module interfaces."""

from __future__ import annotations

from typing import Protocol

from abtp.domain.models import FeatureVector, Prediction, Signal


class StrategyEngine(Protocol):
    """Future strategy engine contract."""

    def generate_signal(
        self, features: FeatureVector, prediction: Prediction | None = None
    ) -> Signal:
        """Generate an explainable signal."""
        ...
