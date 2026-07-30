from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.ai import (
    BASELINE_MODEL_NAME,
    BASELINE_MODEL_VERSION,
    BaselineModelConfig,
    ConservativeBaselineModel,
    DatasetRow,
    ModelLifecycleStatus,
    ModelRegistry,
    ModelRegistryEntry,
    build_feature_dataset,
    registry_entry_from_baseline_metadata,
    training_record_from_baseline_metadata,
    trusted_model_evaluation,
)
from abtp.data import DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, AssetPair
from abtp.features import FeatureSnapshot

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_registry_records_training_and_evaluation_history_from_baseline_metadata() -> None:
    rows = _rows()
    model = ConservativeBaselineModel.fit(
        rows,
        trained_at=NOW + timedelta(hours=1),
        config=BaselineModelConfig(label_horizon_steps=1),
    )
    registry = ModelRegistry()
    entry = registry_entry_from_baseline_metadata(model.metadata)
    training = training_record_from_baseline_metadata(model.metadata, sample_count=len(rows))
    evaluation = trusted_model_evaluation(
        model_name=entry.model_name,
        version=entry.version,
        evaluated_at=NOW + timedelta(hours=2),
        dataset_ref="fixture:validation",
        split_name="validation",
        metrics=model.metadata.metrics,
    )

    registry.register(entry)
    registry.record_training(training)
    registry.record_evaluation(evaluation)

    assert registry.get(BASELINE_MODEL_NAME, BASELINE_MODEL_VERSION) == entry
    assert registry.latest_training(entry.model_ref) == training
    assert registry.latest_evaluation(entry.model_ref) == evaluation
    assert registry.audit_payload()["model_count"] == "1"


def test_duplicate_model_registration_is_rejected() -> None:
    entry = _entry("model-a", "v1")
    registry = ModelRegistry((entry,))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(entry)


def test_retired_model_is_kept_for_audit_but_can_be_filtered_out() -> None:
    registry = ModelRegistry((_entry("model-a", "v1"), _entry("model-b", "v1")))

    registry.mark_retired("model-a", "v1")

    assert [entry.model_ref for entry in registry.list()] == ["model-a:v1", "model-b:v1"]
    assert [entry.model_ref for entry in registry.list(include_retired=False)] == ["model-b:v1"]
    assert registry.get("model-a", "v1").status is ModelLifecycleStatus.RETIRED


def _entry(model_name: str, version: str) -> ModelRegistryEntry:
    from abtp.ai import ModelApprovalStatus

    return ModelRegistryEntry(
        model_name=model_name,
        version=version,
        feature_schema_version="stage-015.v1",
        model_family="baseline",
        label_horizon_steps=1,
        approval_status=ModelApprovalStatus.RESEARCH_APPROVED,
        created_at=NOW,
        limitations=("fixture metadata only",),
    )


def _rows() -> tuple[DatasetRow, ...]:
    snapshots = tuple(
        _snapshot(index, close)
        for index, close in enumerate(("100", "102", "101", "103", "104", "108"))
    )
    return build_feature_dataset(
        snapshots,
        built_at=NOW + timedelta(hours=1),
        label_horizon_steps=1,
    ).rows


def _snapshot(index: int, close: str) -> FeatureSnapshot:
    generated_at = NOW + timedelta(minutes=index)
    return FeatureSnapshot(
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        generated_at=generated_at,
        schema_version="stage-015.v1",
        values={
            "market.close": Decimal(close),
            "market.return_1": Decimal("0.01"),
            "data_quality.flag_count": Decimal("0"),
        },
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref="fixture:features",
            checked_at=generated_at,
        ),
        lookback_start=generated_at - timedelta(minutes=3),
        lookback_end=generated_at,
        source_refs={"candles": f"fixture:candles:{index}"},
    )
