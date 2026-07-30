"""Stable prediction service for research, backtesting, and future strategies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from abtp.ai.baseline import BaselinePrediction
from abtp.ai.explainability import PredictionExplanation, explain_prediction
from abtp.ai.regime import RegimeClassification
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain import AuditEvent, AuditEventType
from abtp.domain.models import JsonValue
from abtp.features import FeatureSnapshot
from abtp.repositories import AuditRepository, IntelligenceRepository


class PredictionModel(Protocol):
    """Model interface required by the Stage 019 prediction service."""

    def predict(self, snapshot: FeatureSnapshot) -> BaselinePrediction:
        """Return probability/confidence output without trading authority."""


@dataclass(frozen=True, slots=True)
class PredictionServiceConfig:
    """Actionability gates for prediction responses."""

    minimum_confidence: Decimal = Decimal("0.30")
    require_trusted_features: bool = True
    require_trusted_regime: bool = False
    persist_predictions: bool = True
    audit_predictions: bool = True

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.minimum_confidence <= Decimal("1"):
            raise ValueError("minimum_confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class PredictionRequest:
    """Input contract for prediction service calls."""

    snapshot: FeatureSnapshot
    regime: RegimeClassification | None = None
    correlation_id: UUID | None = None
    persist: bool = True


@dataclass(frozen=True, slots=True)
class PredictionServiceResult:
    """Auditable prediction response with no signal or order authority."""

    prediction: BaselinePrediction
    explanation: PredictionExplanation
    actionable: bool
    non_actionable_reasons: tuple[str, ...]
    generated_at: datetime
    quality: DataQualityStatus
    prediction_ref: str | None = None
    audit_event_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))

    @property
    def model_version(self) -> str:
        return self.prediction.model_metadata.version

    @property
    def model_name(self) -> str:
        return self.prediction.model_metadata.model_name

    @property
    def confidence(self) -> Decimal:
        return self.prediction.confidence

    @property
    def probability_up(self) -> Decimal:
        return self.prediction.probability_up

    @property
    def probability_down(self) -> Decimal:
        return self.prediction.probability_down

    @property
    def expected_volatility(self) -> Decimal:
        return self.prediction.expected_volatility

    @property
    def flags(self) -> tuple[str, ...]:
        return self.quality.flags

    def to_json_dict(self) -> Mapping[str, JsonValue]:
        """Return a JSON-compatible response for API/UI adapters."""

        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "pair_symbol": self.prediction.pair_symbol,
            "generated_at": self.generated_at.isoformat(),
            "features_ref": self.prediction.features_ref,
            "prediction_ref": self.prediction_ref,
            "audit_event_id": self.audit_event_id,
            "probability_up": str(self.probability_up),
            "probability_down": str(self.probability_down),
            "confidence": str(self.confidence),
            "expected_return": str(self.prediction.expected_return),
            "expected_volatility": str(self.expected_volatility),
            "actionable": self.actionable,
            "non_actionable_reasons": list(self.non_actionable_reasons),
            "quality": self.quality.trust_level.value,
            "flags": list(self.flags),
            "explanation": dict(self.explanation.to_json_dict()),
        }


class PredictionService:
    """Orchestrate model prediction, explainability, gates, persistence, and audit."""

    def __init__(
        self,
        *,
        model: PredictionModel,
        config: PredictionServiceConfig | None = None,
        intelligence_repository: IntelligenceRepository | None = None,
        audit_repository: AuditRepository | None = None,
    ) -> None:
        self._model = model
        self._config = config or PredictionServiceConfig()
        self._intelligence_repository = intelligence_repository
        self._audit_repository = audit_repository

    def predict(self, request: PredictionRequest) -> PredictionServiceResult:
        """Return a gated prediction response and optionally persist audit artifacts."""

        prediction = self._model.predict(request.snapshot)
        reasons = self._non_actionable_reasons(prediction, request)
        quality = self._result_quality(prediction.quality, request.regime, reasons)
        explanation = explain_prediction(
            prediction=prediction,
            snapshot=request.snapshot,
            regime=request.regime,
        )
        actionable = not reasons and quality.is_trusted
        prediction_ref = self._persist_prediction(
            prediction,
            request,
            enabled=request.persist and self._config.persist_predictions,
        )
        audit_event_id = self._append_audit(
            result_prediction=prediction,
            explanation=explanation,
            actionable=actionable,
            non_actionable_reasons=reasons,
            quality=quality,
            prediction_ref=prediction_ref,
            request=request,
        )
        return PredictionServiceResult(
            prediction=prediction,
            explanation=explanation,
            actionable=actionable,
            non_actionable_reasons=reasons,
            generated_at=prediction.generated_at,
            quality=quality,
            prediction_ref=prediction_ref,
            audit_event_id=audit_event_id,
        )

    def _non_actionable_reasons(
        self,
        prediction: BaselinePrediction,
        request: PredictionRequest,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if prediction.confidence < self._config.minimum_confidence:
            reasons.append("prediction confidence is below service threshold")
        if self._config.require_trusted_features and not request.snapshot.quality.is_trusted:
            reasons.append("feature snapshot quality is not trusted")
        if not prediction.quality.is_trusted:
            reasons.append("model output quality is not trusted")
        if (
            self._config.require_trusted_regime
            and request.regime is not None
            and not request.regime.quality.is_trusted
        ):
            reasons.append("regime context quality is not trusted")
        if request.regime is not None and request.regime.risk_adjustment.block_new_entries:
            reasons.append("regime risk context blocks new entries")
        return tuple(dict.fromkeys(reasons))

    def _result_quality(
        self,
        prediction_quality: DataQualityStatus,
        regime: RegimeClassification | None,
        non_actionable_reasons: tuple[str, ...],
    ) -> DataQualityStatus:
        issues = [*prediction_quality.issues]
        if regime is not None:
            issues.extend(regime.quality.issues)
        issues.extend(
            DataQualityIssue(
                flag="non_actionable_prediction",
                severity=DataTrustLevel.DEGRADED,
                reason=reason,
            )
            for reason in non_actionable_reasons
        )
        if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
            trust_level = DataTrustLevel.REJECTED
        elif (
            issues
            or prediction_quality.is_degraded
            or (regime is not None and regime.quality.is_degraded)
        ):
            trust_level = DataTrustLevel.DEGRADED
        else:
            trust_level = DataTrustLevel.TRUSTED
        return DataQualityStatus(
            trust_level=trust_level,
            issues=tuple(issues),
            source_ref="prediction_service",
            checked_at=prediction_quality.checked_at,
        )

    def _persist_prediction(
        self,
        prediction: BaselinePrediction,
        request: PredictionRequest,
        *,
        enabled: bool,
    ) -> str | None:
        if not enabled or self._intelligence_repository is None:
            return None
        return self._intelligence_repository.add_prediction(
            prediction.to_domain_prediction(request.snapshot)
        )

    def _append_audit(
        self,
        *,
        result_prediction: BaselinePrediction,
        explanation: PredictionExplanation,
        actionable: bool,
        non_actionable_reasons: tuple[str, ...],
        quality: DataQualityStatus,
        prediction_ref: str | None,
        request: PredictionRequest,
    ) -> str | None:
        if not self._config.audit_predictions or self._audit_repository is None:
            return None
        event = AuditEvent(
            event_type=AuditEventType.PREDICTION,
            occurred_at=result_prediction.generated_at,
            payload={
                "prediction_ref": prediction_ref or "not_persisted",
                "model_name": result_prediction.model_metadata.model_name,
                "model_version": result_prediction.model_metadata.version,
                "features_ref": result_prediction.features_ref,
                "confidence": str(result_prediction.confidence),
                "probability_up": str(result_prediction.probability_up),
                "probability_down": str(result_prediction.probability_down),
                "actionable": str(actionable),
                "non_actionable_reasons": ",".join(non_actionable_reasons),
                "quality": quality.trust_level.value,
                "regime_label": explanation.regime_label or "not_supplied",
            },
            correlation_id=request.correlation_id,
        )
        return self._audit_repository.append(event)
