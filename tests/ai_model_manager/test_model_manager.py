from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.ai import (
    AIModelManager,
    ModelApprovalStatus,
    ModelEvaluationSnapshot,
    ModelLifecycleStatus,
    ModelManagementRequest,
    ModelRegistry,
    ModelRegistryEntry,
    ModelTrainingRecord,
)
from abtp.config import TradingMode
from abtp.data import DataQualityStatus, DataTrustLevel

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_model_manager_recommends_and_applies_only_safe_mode_selection() -> None:
    registry = _registry()
    manager = AIModelManager(registry)

    report = manager.review(
        ModelManagementRequest(
            mode=TradingMode.PAPER,
            generated_at=NOW,
            source_refs={"operator_review": "fixture:paper"},
        )
    )
    applied = manager.apply_research_or_paper_recommendation(report, mode=TradingMode.PAPER)

    assert report.recommendation.selected_model_ref == "baseline:v2"
    assert applied == "baseline:v2"
    assert manager.active_model_ref == "baseline:v2"
    assert report.audit_payload()["selected_model_ref"] == "baseline:v2"


def test_model_manager_blocks_live_apply_and_has_no_prediction_or_order_authority() -> None:
    manager = AIModelManager(_registry())
    report = manager.review(
        ModelManagementRequest(
            mode=TradingMode.LIVE,
            generated_at=NOW,
            manual_approval_for_live_change=True,
        )
    )

    assert report.recommendation.selected_model_ref == "baseline:v2"
    with pytest.raises(ValueError, match="live active-model changes"):
        manager.apply_research_or_paper_recommendation(report, mode=TradingMode.LIVE)
    with pytest.raises(ValueError, match="cannot serve predictions"):
        manager.predict(object())
    with pytest.raises(ValueError, match="cannot create strategy signals"):
        manager.create_signal(object())
    with pytest.raises(ValueError, match="cannot submit orders"):
        manager.submit_order(object())


def test_public_imports_are_available() -> None:
    import abtp.ai as ai

    assert ai.AIModelManager is AIModelManager


def _registry() -> ModelRegistry:
    registry = ModelRegistry((_entry("v1", Decimal("0.55")), _entry("v2", Decimal("0.72"))))
    for version, accuracy in (("v1", Decimal("0.55")), ("v2", Decimal("0.72"))):
        registry.record_training(_training(version, accuracy))
        registry.record_evaluation(_evaluation(version, accuracy))
    return registry


def _entry(version: str, accuracy: Decimal) -> ModelRegistryEntry:
    status = ModelLifecycleStatus.ACTIVE if version == "v1" else ModelLifecycleStatus.CANDIDATE
    return ModelRegistryEntry(
        model_name="baseline",
        version=version,
        feature_schema_version="stage-015.v1",
        model_family="baseline",
        label_horizon_steps=1,
        status=status,
        approval_status=ModelApprovalStatus.PAPER_APPROVED,
        created_at=NOW,
        limitations=(f"fixture accuracy {accuracy}",),
        source_refs={"model": f"fixture:{version}"},
    )


def _training(version: str, accuracy: Decimal) -> ModelTrainingRecord:
    return ModelTrainingRecord(
        model_name="baseline",
        version=version,
        trained_at=NOW - timedelta(hours=1),
        training_start=NOW - timedelta(days=10),
        training_end=NOW - timedelta(days=1),
        feature_schema_version="stage-015.v1",
        label_horizon_steps=1,
        sample_count=20,
        metrics={"accuracy": accuracy},
        limitations=("fixture training",),
    )


def _evaluation(version: str, accuracy: Decimal) -> ModelEvaluationSnapshot:
    return ModelEvaluationSnapshot(
        model_name="baseline",
        version=version,
        evaluated_at=NOW,
        dataset_ref="fixture:validation",
        split_name="validation",
        metrics={
            "accuracy": accuracy,
            "directional_hit_rate": accuracy,
            "precision_up": Decimal("0.60"),
            "recall_up": Decimal("0.60"),
            "calibration_error": Decimal("0.10"),
        },
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref=f"fixture:evaluation:{version}",
            checked_at=NOW,
        ),
    )
