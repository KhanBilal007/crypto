from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.ai import BaselineModelConfig, ConservativeBaselineModel, build_feature_dataset
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, AssetPair
from abtp.features import FeatureSnapshot

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def pair() -> AssetPair:
    return AssetPair(Asset("BTC"), Asset("USDT"))


def snapshot(index: int, close: str, *, trusted: bool = True) -> FeatureSnapshot:
    generated_at = NOW + timedelta(minutes=index)
    issues = (
        ()
        if trusted
        else (
            DataQualityIssue(
                flag="stale_data",
                severity=DataTrustLevel.REJECTED,
                reason="fixture stale",
            ),
        )
    )
    return FeatureSnapshot(
        pair=pair(),
        generated_at=generated_at,
        schema_version="stage-015.v1",
        values={
            "market.close": Decimal(close),
            "market.return_1": Decimal("0.01") if index else Decimal("0"),
            "data_quality.flag_count": Decimal(len(issues)),
        },
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED if trusted else DataTrustLevel.REJECTED,
            issues=issues,
            source_ref=f"features:{index}",
            checked_at=generated_at,
        ),
        lookback_start=generated_at - timedelta(minutes=3),
        lookback_end=generated_at,
        source_refs={"candles": f"candles:{index}"},
    )


def dataset_rows() -> tuple:
    snapshots = tuple(
        snapshot(index, close)
        for index, close in enumerate(("100", "102", "101", "103", "104", "108"))
    )
    return build_feature_dataset(
        snapshots,
        built_at=NOW + timedelta(hours=1),
        label_horizon_steps=1,
    ).rows


def test_baseline_training_and_prediction_are_deterministic() -> None:
    rows = dataset_rows()
    config = BaselineModelConfig(label_horizon_steps=1)

    model_a = ConservativeBaselineModel.fit(
        rows, trained_at=NOW + timedelta(hours=1), config=config
    )
    model_b = ConservativeBaselineModel.fit(
        rows, trained_at=NOW + timedelta(hours=1), config=config
    )
    prediction_a = model_a.predict(snapshot(6, "109"))
    prediction_b = model_b.predict(snapshot(6, "109"))

    assert model_a.metadata == model_b.metadata
    assert prediction_a.probability_up == prediction_b.probability_up
    assert prediction_a.confidence == prediction_b.confidence
    assert prediction_a.actionable
    assert prediction_a.model_metadata.model_name == "conservative_baseline"
    assert "accuracy" in prediction_a.model_metadata.metrics
    assert not hasattr(prediction_a, "side")
    assert not hasattr(prediction_a, "quantity")


def test_baseline_outputs_domain_prediction_without_order_authority() -> None:
    model = ConservativeBaselineModel.fit(
        dataset_rows(),
        trained_at=NOW + timedelta(hours=1),
        config=BaselineModelConfig(label_horizon_steps=1),
    )
    latest = snapshot(6, "109")
    baseline_prediction = model.predict(latest)
    domain_prediction = baseline_prediction.to_domain_prediction(latest)

    assert domain_prediction.expected_return == baseline_prediction.expected_return
    assert domain_prediction.confidence == baseline_prediction.confidence
    assert domain_prediction.features_ref == latest.inputs_ref
    assert domain_prediction.model_version == "stage-017.v1"


def test_baseline_rejects_empty_training_and_marks_bad_features_non_actionable() -> None:
    with pytest.raises(ValueError, match="actionable training row"):
        ConservativeBaselineModel.fit(
            (),
            trained_at=NOW,
            config=BaselineModelConfig(label_horizon_steps=1),
        )

    model = ConservativeBaselineModel.fit(
        dataset_rows(),
        trained_at=NOW + timedelta(hours=1),
        config=BaselineModelConfig(label_horizon_steps=1),
    )
    prediction = model.predict(snapshot(6, "109", trusted=False))

    assert not prediction.actionable
    assert prediction.quality.is_rejected
