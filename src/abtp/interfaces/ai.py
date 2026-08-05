"""AI module interfaces."""

from __future__ import annotations

from typing import Protocol

from abtp.domain.models import FeatureVector, Prediction


class PredictionEngine(Protocol):
    """Future prediction engine contract."""

    def predict(self, features: FeatureVector) -> Prediction:
        """Generate a prediction from a feature vector."""
        ...
