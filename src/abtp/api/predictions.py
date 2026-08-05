"""Framework-neutral prediction API facade."""

from __future__ import annotations

from collections.abc import Mapping

from abtp.ai import PredictionRequest, PredictionService, PredictionServiceResult
from abtp.ai.regime import RegimeClassification
from abtp.domain.models import JsonValue
from abtp.features import FeatureSnapshot


class PredictionAPI:
    """Small facade future HTTP/UI adapters can wrap without model internals."""

    def __init__(self, service: PredictionService) -> None:
        self._service = service

    def predict(
        self,
        snapshot: FeatureSnapshot,
        *,
        regime: RegimeClassification | None = None,
        persist: bool = True,
    ) -> PredictionServiceResult:
        """Request a prediction from a feature snapshot and optional regime context."""

        return self._service.predict(
            PredictionRequest(snapshot=snapshot, regime=regime, persist=persist)
        )


def prediction_response_to_json(
    result: PredictionServiceResult,
) -> Mapping[str, JsonValue]:
    """Serialize a prediction response for API tests and future adapters."""

    return result.to_json_dict()
