from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection
from uuid import UUID

from abtp.ai import (
    BaselineModelConfig,
    ConservativeBaselineModel,
    MarketRegimeClassifier,
    MarketRegimeLabel,
    PredictionExplanation,
    PredictionRequest,
    PredictionService,
    PredictionServiceConfig,
    build_feature_dataset,
    data_quality_score,
    feature_names_from_importance,
)
from abtp.api import PredictionAPI, prediction_response_to_json
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, AssetPair
from abtp.features import FEATURE_SCHEMA_VERSION, FeatureSnapshot
from abtp.repositories import AuditRepository, IntelligenceRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_prediction_service_persists_prediction_and_audit(
    migrated_connection: Connection,
) -> None:
    service = PredictionService(
        model=_model(),
        config=PredictionServiceConfig(minimum_confidence=Decimal("0.30")),
        intelligence_repository=IntelligenceRepository(migrated_connection),
        audit_repository=AuditRepository(migrated_connection),
    )
    snapshot = _snapshot(6, "109", return_1=Decimal("0.01"), return_3=Decimal("0.02"))
    regime = MarketRegimeClassifier().classify(snapshot)
    correlation_id = UUID("00000000-0000-0000-0000-000000000019")

    result = service.predict(
        PredictionRequest(snapshot=snapshot, regime=regime, correlation_id=correlation_id)
    )

    assert result.actionable
    assert result.prediction_ref is not None
    assert result.audit_event_id is not None
    stored_prediction = IntelligenceRepository(migrated_connection).get_prediction(
        result.prediction_ref
    )
    audit_events = AuditRepository(migrated_connection).list_by_correlation(str(correlation_id))
    assert stored_prediction is not None
    assert stored_prediction.model_version == result.model_version
    assert stored_prediction.features_ref == snapshot.inputs_ref
    assert len(audit_events) == 1
    assert audit_events[0].payload["model_version"] == result.model_version
    assert audit_events[0].payload["actionable"] == "True"


def test_low_confidence_prediction_is_non_actionable_without_order_authority() -> None:
    service = PredictionService(
        model=_model(),
        config=PredictionServiceConfig(minimum_confidence=Decimal("0.80")),
    )

    result = service.predict(PredictionRequest(snapshot=_snapshot(6, "109")))

    assert not result.actionable
    assert "prediction confidence is below service threshold" in result.non_actionable_reasons
    assert result.quality.is_degraded
    assert "non_actionable_prediction" in result.flags
    assert not hasattr(result, "signal")
    assert not hasattr(result, "order_intent")
    assert not hasattr(result, "risk_decision")


def test_degraded_feature_inputs_are_non_actionable_and_explained() -> None:
    service = PredictionService(model=_model())
    snapshot = _snapshot(
        6,
        "109",
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.DEGRADED,
            issues=(
                DataQualityIssue(
                    flag="degraded_feed",
                    severity=DataTrustLevel.DEGRADED,
                    reason="fixture degraded",
                ),
            ),
            source_ref="features:degraded",
            checked_at=NOW,
        ),
    )

    result = service.predict(PredictionRequest(snapshot=snapshot))

    assert not result.actionable
    assert result.quality.is_degraded
    assert result.explanation.data_quality_score < Decimal("1")
    assert "feature snapshot quality is not trusted" in result.non_actionable_reasons


def test_regime_block_marks_prediction_non_actionable() -> None:
    service = PredictionService(model=_model())
    snapshot = _snapshot(6, "109", return_1=Decimal("-0.09"))
    regime = MarketRegimeClassifier().classify(snapshot)

    result = service.predict(PredictionRequest(snapshot=snapshot, regime=regime))

    assert regime.label is MarketRegimeLabel.SHOCK
    assert not result.actionable
    assert "regime risk context blocks new entries" in result.non_actionable_reasons
    assert result.explanation.regime_label == MarketRegimeLabel.SHOCK.value


def test_explanation_and_api_response_are_stable() -> None:
    service = PredictionService(
        model=_model(), config=PredictionServiceConfig(audit_predictions=False)
    )
    api = PredictionAPI(service)
    result = api.predict(_snapshot(6, "109"), persist=False)
    payload = prediction_response_to_json(result)

    assert isinstance(result.explanation, PredictionExplanation)
    assert payload["model_version"] == "stage-017.v1"
    assert payload["prediction_ref"] is None
    assert payload["actionable"] is True
    assert "feature_importance" in dict(payload["explanation"])
    assert "market.return_1" in feature_names_from_importance(result.explanation.feature_importance)
    assert data_quality_score(result.quality) == Decimal("1")


def _model() -> ConservativeBaselineModel:
    snapshots = tuple(
        _snapshot(index, close)
        for index, close in enumerate(("100", "102", "101", "103", "104", "108"))
    )
    rows = build_feature_dataset(
        snapshots,
        built_at=NOW + timedelta(hours=1),
        label_horizon_steps=1,
    ).rows
    return ConservativeBaselineModel.fit(
        rows,
        trained_at=NOW + timedelta(hours=1),
        config=BaselineModelConfig(label_horizon_steps=1),
    )


def _snapshot(
    index: int,
    close: str,
    *,
    return_1: Decimal = Decimal("0.01"),
    return_3: Decimal = Decimal("0.02"),
    quality: DataQualityStatus | None = None,
) -> FeatureSnapshot:
    generated_at = NOW + timedelta(minutes=index)
    return FeatureSnapshot(
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        generated_at=generated_at,
        schema_version=FEATURE_SCHEMA_VERSION,
        values={
            "market.close": Decimal(close),
            "market.return_1": return_1,
            "market.return_3": return_3,
            "market.volume_ratio": Decimal("1.0"),
            "indicator.sma.sma": Decimal("100"),
            "indicator.rsi.rsi": Decimal("58"),
            "indicator.atr.atr_pct": Decimal("0.010"),
            "data_quality.flag_count": Decimal("0"),
            "liquidity.spread_bps": Decimal("10"),
        },
        quality=quality or _trusted_quality(generated_at),
        lookback_start=generated_at - timedelta(minutes=3),
        lookback_end=generated_at,
        source_refs={"candles": f"fixture:candles:{index}"},
    )


def _trusted_quality(checked_at: datetime) -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="features:trusted",
        checked_at=checked_at,
    )
