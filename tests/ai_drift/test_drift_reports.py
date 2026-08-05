from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.ai import (
    DriftAssessment,
    DriftSeverity,
    DriftWindow,
    ModelDriftReport,
    assess_model_drift,
    build_model_drift_report,
)
from abtp.data import DataQualityStatus, DataTrustLevel

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_drift_report_collects_downgrade_and_retraining_recommendations() -> None:
    assessment = assess_model_drift(
        _window("baseline", confidence=Decimal("0.80"), accuracy=Decimal("0.72")),
        _window("current", confidence=Decimal("0.18"), accuracy=Decimal("0.42")),
        generated_at=NOW + timedelta(hours=1),
    )

    report = build_model_drift_report((assessment,), generated_at=NOW + timedelta(hours=1))

    assert isinstance(report, ModelDriftReport)
    assert report.quality.is_rejected
    assert report.downgrade_recommendations == ("baseline:v1",)
    assert report.retraining_recommendations == ("baseline:v1",)
    assert report.non_actionable_models == ("baseline:v1",)
    assert report.audit_payload()["assessment_count"] == "1"


def test_clean_report_remains_trusted_and_advisory_only() -> None:
    assessment = assess_model_drift(
        _window("baseline", confidence=Decimal("0.60"), accuracy=Decimal("0.62")),
        _window("current", confidence=Decimal("0.58"), accuracy=Decimal("0.60")),
        generated_at=NOW + timedelta(hours=1),
    )

    report = build_model_drift_report((assessment,), generated_at=NOW + timedelta(hours=1))

    assert report.quality.is_trusted
    assert report.downgrade_recommendations == ()
    assert report.retraining_recommendations == ()
    with pytest.raises(ValueError, match="cannot train models"):
        report.train_model()
    with pytest.raises(ValueError, match="cannot create strategy signals"):
        report.create_signal()
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()


def test_report_requires_assessments() -> None:
    with pytest.raises(ValueError, match="at least one drift assessment"):
        build_model_drift_report((), generated_at=NOW)


def test_public_imports_expose_stage_043_contracts() -> None:
    assert DriftAssessment.__name__ == "DriftAssessment"
    assert DriftSeverity.SEVERE.value == "severe"


def _window(name: str, *, confidence: Decimal, accuracy: Decimal) -> DriftWindow:
    return DriftWindow(
        model_ref="baseline:v1",
        name=name,
        started_at=NOW,
        ended_at=NOW + timedelta(minutes=3),
        feature_values={"market.return_1": (Decimal("0.010"), Decimal("0.011"))},
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref=f"fixture:{name}",
            checked_at=NOW,
        ),
        prediction_confidences=(confidence, confidence, confidence),
        outcome_accuracy=accuracy,
        directional_hit_rate=accuracy,
        calibration_error=Decimal("0.10"),
        label_distribution={"up": Decimal("0.50"), "down": Decimal("0.50")},
        source_refs={"fixture": name},
    )
