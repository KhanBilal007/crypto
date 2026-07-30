from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.ai import (
    ActiveModelRecommendation,
    ModelApprovalStatus,
    ModelEvaluationSnapshot,
    ModelLifecycleStatus,
    ModelRegistryEntry,
    ModelSelectionInput,
    ModelTrainingRecord,
    compare_model_candidates,
    select_active_model,
    trusted_model_evaluation,
)
from abtp.config import TradingMode
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_model_comparison_ranks_by_validation_metrics() -> None:
    ranked = compare_model_candidates(
        (
            _candidate("baseline", "v1", accuracy=Decimal("0.55")),
            _candidate("baseline", "v2", accuracy=Decimal("0.72")),
        ),
        generated_at=NOW,
    )

    assert [item.model_ref for item in ranked] == ["baseline:v2", "baseline:v1"]
    assert ranked[0].eligible
    assert "accuracy=0.72" in ranked[0].evidence


def test_stale_or_rejected_evaluation_fails_closed() -> None:
    stale = _candidate(
        "baseline",
        "stale",
        evaluated_at=NOW - timedelta(days=45),
        accuracy=Decimal("0.90"),
    )
    rejected = _candidate(
        "baseline",
        "rejected",
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.REJECTED,
            issues=(
                DataQualityIssue(
                    flag="bad_eval",
                    severity=DataTrustLevel.REJECTED,
                    reason="fixture rejected evaluation",
                ),
            ),
            source_ref="fixture:evaluation",
            checked_at=NOW,
        ),
    )

    ranked = compare_model_candidates((stale, rejected), generated_at=NOW)

    assert "evaluation snapshot is stale" in ranked[0].rejected_reasons
    assert any("evaluation quality is not trusted" in item.rejected_reasons for item in ranked)
    assert any(item.quality.is_rejected for item in ranked)


def test_live_active_model_selection_requires_manual_approval() -> None:
    recommendation = select_active_model(
        (_candidate("baseline", "v2", accuracy=Decimal("0.72")),),
        mode=TradingMode.LIVE,
        generated_at=NOW,
        manual_approval_for_live_change=False,
    )

    assert isinstance(recommendation, ActiveModelRecommendation)
    assert recommendation.selected_model_ref is None
    assert recommendation.manual_approval_required
    assert "manual approval required before live active-model change" in (
        recommendation.rejected_reasons
    )


def test_research_selection_can_apply_without_live_swap() -> None:
    recommendation = select_active_model(
        (_candidate("baseline", "v2", accuracy=Decimal("0.72")),),
        mode=TradingMode.RESEARCH,
        generated_at=NOW,
    )

    assert recommendation.selected_model_ref == "baseline:v2"
    assert recommendation.can_apply_without_live_swap
    assert recommendation.audit_payload()["selected_model_ref"] == "baseline:v2"


def test_retired_model_is_not_eligible_even_with_good_metrics() -> None:
    recommendation = select_active_model(
        (
            _candidate(
                "baseline",
                "retired",
                accuracy=Decimal("0.90"),
                status=ModelLifecycleStatus.RETIRED,
            ),
        ),
        mode=TradingMode.PAPER,
        generated_at=NOW,
    )

    assert recommendation.selected_model_ref is None
    assert "model lifecycle status is retired" in recommendation.ranked_models[0].rejected_reasons


def _candidate(
    model_name: str,
    version: str,
    *,
    accuracy: Decimal = Decimal("0.65"),
    evaluated_at: datetime = NOW,
    status: ModelLifecycleStatus = ModelLifecycleStatus.CANDIDATE,
    quality: DataQualityStatus | None = None,
) -> ModelSelectionInput:
    entry = ModelRegistryEntry(
        model_name=model_name,
        version=version,
        feature_schema_version="stage-015.v1",
        model_family="baseline",
        label_horizon_steps=1,
        status=status,
        approval_status=ModelApprovalStatus.PAPER_APPROVED,
        created_at=NOW,
        limitations=("fixture metadata only",),
        source_refs={"model": f"fixture:{model_name}:{version}"},
    )
    training = ModelTrainingRecord(
        model_name=model_name,
        version=version,
        trained_at=NOW - timedelta(hours=1),
        training_start=NOW - timedelta(days=10),
        training_end=NOW - timedelta(days=1),
        feature_schema_version="stage-015.v1",
        label_horizon_steps=1,
        sample_count=20,
        metrics={"accuracy": accuracy},
        limitations=("fixture metadata only",),
    )
    evaluation = ModelEvaluationSnapshot(
        model_name=model_name,
        version=version,
        evaluated_at=evaluated_at,
        dataset_ref="fixture:validation",
        split_name="validation",
        metrics={
            "accuracy": accuracy,
            "directional_hit_rate": accuracy,
            "precision_up": Decimal("0.60"),
            "recall_up": Decimal("0.60"),
            "calibration_error": Decimal("0.10"),
        },
        quality=quality
        or trusted_model_evaluation(
            model_name=model_name,
            version=version,
            evaluated_at=evaluated_at,
            dataset_ref="fixture:validation",
            split_name="validation",
            metrics={"accuracy": accuracy},
        ).quality,
    )
    return ModelSelectionInput(
        entry=entry,
        latest_training=training,
        latest_evaluation=evaluation,
        source_refs={"selection": f"fixture:{model_name}:{version}"},
    )
