from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.ai import (
    DriftRuleThresholds,
    DriftSeverity,
    DriftWindow,
    assess_model_drift,
    drift_window_from_feature_snapshots,
)
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, AssetPair
from abtp.features import FeatureSnapshot

NOW = datetime(2026, 1, 1, tzinfo=UTC)
MODEL_REF = "baseline:v1"


def test_feature_drift_recommends_retraining_without_direct_downgrade() -> None:
    baseline = _window(
        "baseline",
        values={"market.return_1": ("0.010", "0.011", "0.009")},
    )
    current = _window(
        "current",
        values={"market.return_1": ("0.012", "0.013", "0.014")},
    )

    assessment = assess_model_drift(
        baseline,
        current,
        generated_at=NOW + timedelta(hours=1),
        required_feature_names=("market.return_1",),
    )

    assert assessment.severity is DriftSeverity.MODERATE
    assert assessment.retraining_recommended
    assert not assessment.downgrade_recommended
    assert not assessment.non_actionable
    assert any(
        measurement.metric_name == "market.return_1.mean_shift_pct"
        for measurement in assessment.measurements
    )


def test_concept_drift_proxy_from_label_distribution_recommends_retraining() -> None:
    baseline = _window(
        "baseline",
        label_distribution={"up": Decimal("0.60"), "down": Decimal("0.40")},
    )
    current = _window(
        "current",
        label_distribution={"up": Decimal("0.20"), "down": Decimal("0.80")},
    )

    assessment = assess_model_drift(baseline, current, generated_at=NOW + timedelta(hours=1))

    assert assessment.severity is DriftSeverity.SEVERE
    assert assessment.retraining_recommended
    assert assessment.downgrade_recommended
    assert any(
        measurement.metric_name == "label_distribution.up"
        and measurement.severity is DriftSeverity.MODERATE
        for measurement in assessment.measurements
    )


def test_confidence_degradation_produces_downgrade_recommendation() -> None:
    baseline = _window(
        "baseline",
        prediction_confidences=(Decimal("0.75"), Decimal("0.80"), Decimal("0.70")),
    )
    current = _window(
        "current",
        prediction_confidences=(Decimal("0.20"), Decimal("0.22"), Decimal("0.18")),
    )

    assessment = assess_model_drift(baseline, current, generated_at=NOW + timedelta(hours=1))

    assert assessment.severity is DriftSeverity.SEVERE
    assert assessment.downgrade is not None
    assert assessment.downgrade.recommended_status == "degraded"
    assert assessment.non_actionable
    assert "average prediction confidence degraded" in assessment.downgrade.reasons


def test_prediction_quality_degradation_and_calibration_are_explainable() -> None:
    baseline = _window(
        "baseline",
        outcome_accuracy=Decimal("0.72"),
        directional_hit_rate=Decimal("0.70"),
        calibration_error=Decimal("0.08"),
    )
    current = _window(
        "current",
        outcome_accuracy=Decimal("0.45"),
        directional_hit_rate=Decimal("0.48"),
        calibration_error=Decimal("0.40"),
    )

    assessment = assess_model_drift(baseline, current, generated_at=NOW + timedelta(hours=1))

    assert assessment.downgrade_recommended
    assert assessment.quality.is_rejected
    assert assessment.audit_payload()["downgrade_recommended"] == "True"
    assert any("allowed_drop=0.10" in item.evidence for item in assessment.measurements)


def test_stale_or_rejected_current_window_fails_safe() -> None:
    rejected_quality = DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_features",
                severity=DataTrustLevel.REJECTED,
                reason="fixture rejected current drift window",
            ),
        ),
        source_ref="fixture:quality",
        checked_at=NOW,
    )
    baseline = _window("baseline")
    current = _window(
        "current",
        started_at=NOW - timedelta(days=11),
        ended_at=NOW - timedelta(days=10),
        quality=rejected_quality,
    )

    assessment = assess_model_drift(
        baseline,
        current,
        generated_at=NOW + timedelta(hours=1),
        thresholds=DriftRuleThresholds(max_window_age=timedelta(days=1)),
    )

    assert assessment.downgrade_recommended
    assert assessment.non_actionable
    assert "data_quality" in assessment.quality.flags


def test_drift_window_can_be_built_from_feature_snapshots() -> None:
    snapshots = (
        _snapshot(Decimal("100"), NOW),
        _snapshot(Decimal("101"), NOW + timedelta(minutes=1)),
    )

    window = drift_window_from_feature_snapshots(
        model_ref=MODEL_REF,
        name="baseline",
        snapshots=snapshots,
        feature_names=("market.close",),
    )

    assert window.model_ref == MODEL_REF
    assert window.sample_count == 2
    assert window.feature_values["market.close"] == (Decimal("100"), Decimal("101"))
    assert window.quality.is_trusted


def _window(
    name: str,
    *,
    values: dict[str, tuple[str, ...]] | None = None,
    prediction_confidences: tuple[Decimal, ...] = (),
    outcome_accuracy: Decimal | None = Decimal("0.65"),
    directional_hit_rate: Decimal | None = Decimal("0.64"),
    calibration_error: Decimal | None = Decimal("0.10"),
    label_distribution: dict[str, Decimal] | None = None,
    quality: DataQualityStatus | None = None,
    started_at: datetime = NOW,
    ended_at: datetime = NOW,
) -> DriftWindow:
    raw_values = values or {"market.return_1": ("0.010", "0.011", "0.009")}
    return DriftWindow(
        model_ref=MODEL_REF,
        name=name,
        started_at=started_at,
        ended_at=ended_at,
        feature_values={
            feature_name: tuple(Decimal(value) for value in series)
            for feature_name, series in raw_values.items()
        },
        quality=quality or _trusted_quality(),
        prediction_confidences=prediction_confidences,
        outcome_accuracy=outcome_accuracy,
        directional_hit_rate=directional_hit_rate,
        calibration_error=calibration_error,
        label_distribution=label_distribution or {"up": Decimal("0.50"), "down": Decimal("0.50")},
        source_refs={"fixture": name},
    )


def _snapshot(close: Decimal, generated_at: datetime) -> FeatureSnapshot:
    return FeatureSnapshot(
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        generated_at=generated_at,
        schema_version="stage-015.v1",
        values={"market.close": close},
        quality=_trusted_quality(),
        lookback_start=generated_at - timedelta(minutes=1),
        lookback_end=generated_at,
        source_refs={"features": f"fixture:{close}"},
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:trusted",
        checked_at=NOW,
    )
