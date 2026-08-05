"""Deterministic model drift and degradation rules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from abtp.ai.drift import (
    DECIMAL_ONE,
    DECIMAL_ZERO,
    DowngradeRecommendation,
    DriftAssessment,
    DriftKind,
    DriftMeasurement,
    DriftSeverity,
    DriftWindow,
    RetrainingRecommendation,
)
from abtp.ai.model_registry import ModelLifecycleStatus
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp


@dataclass(frozen=True, slots=True)
class DriftRuleThresholds:
    """Conservative Stage 043 drift thresholds."""

    feature_mean_shift_pct: Decimal = Decimal("0.20")
    distribution_variance_shift_pct: Decimal = Decimal("0.50")
    accuracy_drop: Decimal = Decimal("0.10")
    directional_hit_rate_drop: Decimal = Decimal("0.10")
    calibration_error_increase: Decimal = Decimal("0.15")
    confidence_drop: Decimal = Decimal("0.15")
    min_current_confidence: Decimal = Decimal("0.25")
    label_distribution_shift: Decimal = Decimal("0.25")
    max_window_age: timedelta = timedelta(days=7)
    severe_multiplier: Decimal = Decimal("2")
    severe_measurement_count: int = 2
    policy_version: str = "stage-043.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("feature_mean_shift_pct", self.feature_mean_shift_pct),
            ("distribution_variance_shift_pct", self.distribution_variance_shift_pct),
            ("accuracy_drop", self.accuracy_drop),
            ("directional_hit_rate_drop", self.directional_hit_rate_drop),
            ("calibration_error_increase", self.calibration_error_increase),
            ("confidence_drop", self.confidence_drop),
            ("min_current_confidence", self.min_current_confidence),
            ("label_distribution_shift", self.label_distribution_shift),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_window_age < timedelta(0):
            raise ValueError("max_window_age cannot be negative")
        if self.severe_multiplier < DECIMAL_ONE:
            raise ValueError("severe_multiplier must be at least 1")
        if self.severe_measurement_count <= 0:
            raise ValueError("severe_measurement_count must be positive")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


def assess_model_drift(
    baseline_window: DriftWindow,
    current_window: DriftWindow,
    *,
    generated_at: datetime,
    thresholds: DriftRuleThresholds | None = None,
    required_feature_names: Sequence[str] = (),
    source_refs: Mapping[str, str] | None = None,
) -> DriftAssessment:
    """Assess model drift without changing registry state or running models."""

    if baseline_window.model_ref != current_window.model_ref:
        raise ValueError("drift windows must belong to the same model_ref")
    active_thresholds = thresholds or DriftRuleThresholds()
    checked_at = normalize_timestamp(generated_at)
    refs = _source_refs(baseline_window, current_window, source_refs or {})
    measurements: list[DriftMeasurement] = []
    measurements.extend(
        _feature_measurements(
            baseline_window,
            current_window,
            thresholds=active_thresholds,
            required_feature_names=required_feature_names,
            source_refs=refs,
        )
    )
    measurements.extend(
        _prediction_quality_measurements(
            baseline_window,
            current_window,
            thresholds=active_thresholds,
            source_refs=refs,
        )
    )
    measurements.extend(
        _confidence_measurements(
            baseline_window,
            current_window,
            thresholds=active_thresholds,
            source_refs=refs,
        )
    )
    measurements.extend(
        _data_quality_measurements(
            baseline_window,
            current_window,
            generated_at=checked_at,
            thresholds=active_thresholds,
            source_refs=refs,
        )
    )
    if not measurements:
        measurements.append(
            DriftMeasurement(
                kind=DriftKind.DATA_QUALITY,
                metric_name="no_drift_inputs",
                baseline_value=None,
                current_value=None,
                delta=DECIMAL_ZERO,
                threshold=DECIMAL_ZERO,
                severity=DriftSeverity.NONE,
                reason="no comparable drift inputs were supplied",
                evidence=("model drift assessment has no comparable metrics",),
                source_refs=refs,
            )
        )
    severity = _aggregate_severity(tuple(measurements), active_thresholds)
    quality = _assessment_quality(
        tuple(measurements),
        baseline_window=baseline_window,
        current_window=current_window,
        checked_at=checked_at,
    )
    downgrade = _downgrade_recommendation(
        current_window.model_ref,
        tuple(measurements),
        severity=severity,
        quality=quality,
        source_refs=refs,
    )
    retraining = _retraining_recommendation(
        current_window.model_ref,
        current_window,
        tuple(measurements),
        severity=severity,
        source_refs=refs,
    )
    return DriftAssessment(
        model_ref=current_window.model_ref,
        generated_at=checked_at,
        baseline_window=baseline_window,
        current_window=current_window,
        measurements=tuple(measurements),
        severity=severity,
        quality=quality,
        downgrade=downgrade,
        retraining=retraining,
        non_actionable=downgrade is not None or quality.is_rejected,
        policy_version=active_thresholds.policy_version,
        source_refs=refs,
    )


def _feature_measurements(
    baseline: DriftWindow,
    current: DriftWindow,
    *,
    thresholds: DriftRuleThresholds,
    required_feature_names: Sequence[str],
    source_refs: Mapping[str, str],
) -> tuple[DriftMeasurement, ...]:
    measurements: list[DriftMeasurement] = []
    common_features = tuple(sorted(set(baseline.feature_values) & set(current.feature_values)))
    for required_name in required_feature_names:
        if required_name not in common_features:
            measurements.append(
                DriftMeasurement(
                    kind=DriftKind.FEATURE,
                    metric_name=f"{required_name}.missing",
                    baseline_value=None,
                    current_value=None,
                    delta=None,
                    threshold=DECIMAL_ZERO,
                    severity=DriftSeverity.SEVERE,
                    reason=f"required drift feature is missing: {required_name}",
                    evidence=(f"{required_name} absent from baseline or current drift window",),
                    source_refs=source_refs,
                )
            )
    for feature_name in common_features:
        baseline_values = baseline.feature_values[feature_name]
        current_values = current.feature_values[feature_name]
        baseline_mean = _mean(baseline_values)
        current_mean = _mean(current_values)
        mean_shift = _relative_delta(baseline_mean, current_mean)
        measurements.append(
            DriftMeasurement(
                kind=DriftKind.FEATURE,
                metric_name=f"{feature_name}.mean_shift_pct",
                baseline_value=baseline_mean,
                current_value=current_mean,
                delta=mean_shift,
                threshold=thresholds.feature_mean_shift_pct,
                severity=_threshold_severity(
                    mean_shift, thresholds.feature_mean_shift_pct, thresholds
                ),
                reason=f"feature mean shift for {feature_name}",
                evidence=(
                    f"baseline_mean={baseline_mean}",
                    f"current_mean={current_mean}",
                    f"threshold={thresholds.feature_mean_shift_pct}",
                ),
                source_refs=source_refs,
            )
        )
        baseline_variance = _variance(baseline_values)
        current_variance = _variance(current_values)
        variance_shift = _relative_delta(baseline_variance, current_variance)
        measurements.append(
            DriftMeasurement(
                kind=DriftKind.DISTRIBUTION,
                metric_name=f"{feature_name}.variance_shift_pct",
                baseline_value=baseline_variance,
                current_value=current_variance,
                delta=variance_shift,
                threshold=thresholds.distribution_variance_shift_pct,
                severity=_threshold_severity(
                    variance_shift, thresholds.distribution_variance_shift_pct, thresholds
                ),
                reason=f"feature variance shift for {feature_name}",
                evidence=(
                    f"baseline_variance={baseline_variance}",
                    f"current_variance={current_variance}",
                    f"threshold={thresholds.distribution_variance_shift_pct}",
                ),
                source_refs=source_refs,
            )
        )
    return tuple(measurements)


def _prediction_quality_measurements(
    baseline: DriftWindow,
    current: DriftWindow,
    *,
    thresholds: DriftRuleThresholds,
    source_refs: Mapping[str, str],
) -> tuple[DriftMeasurement, ...]:
    measurements: list[DriftMeasurement] = []
    for metric_name, baseline_value, current_value, threshold in (
        (
            "outcome_accuracy_drop",
            baseline.outcome_accuracy,
            current.outcome_accuracy,
            thresholds.accuracy_drop,
        ),
        (
            "directional_hit_rate_drop",
            baseline.directional_hit_rate,
            current.directional_hit_rate,
            thresholds.directional_hit_rate_drop,
        ),
    ):
        if baseline_value is None or current_value is None:
            continue
        drop = max(DECIMAL_ZERO, baseline_value - current_value)
        measurements.append(
            DriftMeasurement(
                kind=DriftKind.PREDICTION_QUALITY,
                metric_name=metric_name,
                baseline_value=baseline_value,
                current_value=current_value,
                delta=drop,
                threshold=threshold,
                severity=_threshold_severity(drop, threshold, thresholds),
                reason=f"prediction quality metric degraded: {metric_name}",
                evidence=(
                    f"baseline={baseline_value}",
                    f"current={current_value}",
                    f"allowed_drop={threshold}",
                ),
                source_refs=source_refs,
            )
        )
    if baseline.calibration_error is not None and current.calibration_error is not None:
        increase = max(DECIMAL_ZERO, current.calibration_error - baseline.calibration_error)
        measurements.append(
            DriftMeasurement(
                kind=DriftKind.PREDICTION_QUALITY,
                metric_name="calibration_error_increase",
                baseline_value=baseline.calibration_error,
                current_value=current.calibration_error,
                delta=increase,
                threshold=thresholds.calibration_error_increase,
                severity=_threshold_severity(
                    increase, thresholds.calibration_error_increase, thresholds
                ),
                reason="prediction calibration error increased",
                evidence=(
                    f"baseline_calibration_error={baseline.calibration_error}",
                    f"current_calibration_error={current.calibration_error}",
                    f"threshold={thresholds.calibration_error_increase}",
                ),
                source_refs=source_refs,
            )
        )
    measurements.extend(
        _label_distribution_measurements(
            baseline, current, thresholds=thresholds, source_refs=source_refs
        )
    )
    return tuple(measurements)


def _label_distribution_measurements(
    baseline: DriftWindow,
    current: DriftWindow,
    *,
    thresholds: DriftRuleThresholds,
    source_refs: Mapping[str, str],
) -> tuple[DriftMeasurement, ...]:
    labels = tuple(sorted(set(baseline.label_distribution) | set(current.label_distribution)))
    return tuple(
        DriftMeasurement(
            kind=DriftKind.CONCEPT_PROXY,
            metric_name=f"label_distribution.{label}",
            baseline_value=baseline.label_distribution.get(label, DECIMAL_ZERO),
            current_value=current.label_distribution.get(label, DECIMAL_ZERO),
            delta=abs(
                current.label_distribution.get(label, DECIMAL_ZERO)
                - baseline.label_distribution.get(label, DECIMAL_ZERO)
            ),
            threshold=thresholds.label_distribution_shift,
            severity=_threshold_severity(
                abs(
                    current.label_distribution.get(label, DECIMAL_ZERO)
                    - baseline.label_distribution.get(label, DECIMAL_ZERO)
                ),
                thresholds.label_distribution_shift,
                thresholds,
            ),
            reason=f"label distribution shifted for {label}",
            evidence=(
                f"baseline_share={baseline.label_distribution.get(label, DECIMAL_ZERO)}",
                f"current_share={current.label_distribution.get(label, DECIMAL_ZERO)}",
                f"threshold={thresholds.label_distribution_shift}",
            ),
            source_refs=source_refs,
        )
        for label in labels
    )


def _confidence_measurements(
    baseline: DriftWindow,
    current: DriftWindow,
    *,
    thresholds: DriftRuleThresholds,
    source_refs: Mapping[str, str],
) -> tuple[DriftMeasurement, ...]:
    baseline_confidence = baseline.average_confidence
    current_confidence = current.average_confidence
    if baseline_confidence is None or current_confidence is None:
        return ()
    drop = max(DECIMAL_ZERO, baseline_confidence - current_confidence)
    severity = _threshold_severity(drop, thresholds.confidence_drop, thresholds)
    if current_confidence < thresholds.min_current_confidence:
        severity = DriftSeverity.SEVERE
    return (
        DriftMeasurement(
            kind=DriftKind.CONFIDENCE,
            metric_name="average_confidence_drop",
            baseline_value=baseline_confidence,
            current_value=current_confidence,
            delta=drop,
            threshold=thresholds.confidence_drop,
            severity=severity,
            reason="average prediction confidence degraded",
            evidence=(
                f"baseline_average_confidence={baseline_confidence}",
                f"current_average_confidence={current_confidence}",
                f"drop_threshold={thresholds.confidence_drop}",
                f"minimum_current_confidence={thresholds.min_current_confidence}",
            ),
            source_refs=source_refs,
        ),
    )


def _data_quality_measurements(
    baseline: DriftWindow,
    current: DriftWindow,
    *,
    generated_at: datetime,
    thresholds: DriftRuleThresholds,
    source_refs: Mapping[str, str],
) -> tuple[DriftMeasurement, ...]:
    measurements: list[DriftMeasurement] = []
    if baseline.quality.is_rejected:
        measurements.append(
            _quality_measurement(
                "baseline_window_quality",
                DriftSeverity.MODERATE,
                "baseline drift window quality is rejected",
                baseline.quality.flags,
                source_refs,
            )
        )
    if current.quality.is_rejected:
        measurements.append(
            _quality_measurement(
                "current_window_quality",
                DriftSeverity.SEVERE,
                "current drift window quality is rejected",
                current.quality.flags,
                source_refs,
            )
        )
    elif current.quality.is_degraded:
        measurements.append(
            _quality_measurement(
                "current_window_quality",
                DriftSeverity.MODERATE,
                "current drift window quality is degraded",
                current.quality.flags,
                source_refs,
            )
        )
    age = normalize_timestamp(generated_at) - current.ended_at
    if age > thresholds.max_window_age:
        measurements.append(
            DriftMeasurement(
                kind=DriftKind.DATA_QUALITY,
                metric_name="current_window_age",
                baseline_value=None,
                current_value=Decimal(str(age.total_seconds())),
                delta=Decimal(str(age.total_seconds())),
                threshold=Decimal(str(thresholds.max_window_age.total_seconds())),
                severity=DriftSeverity.SEVERE,
                reason="current drift window is stale",
                evidence=(
                    f"current_ended_at={current.ended_at.isoformat()}",
                    f"generated_at={normalize_timestamp(generated_at).isoformat()}",
                    f"max_window_age={thresholds.max_window_age}",
                ),
                source_refs=source_refs,
            )
        )
    return tuple(measurements)


def _quality_measurement(
    metric_name: str,
    severity: DriftSeverity,
    reason: str,
    flags: tuple[str, ...],
    source_refs: Mapping[str, str],
) -> DriftMeasurement:
    return DriftMeasurement(
        kind=DriftKind.DATA_QUALITY,
        metric_name=metric_name,
        baseline_value=None,
        current_value=None,
        delta=None,
        threshold=DECIMAL_ZERO,
        severity=severity,
        reason=reason,
        evidence=flags or ("quality status is not trusted",),
        source_refs=source_refs,
    )


def _aggregate_severity(
    measurements: Sequence[DriftMeasurement], thresholds: DriftRuleThresholds
) -> DriftSeverity:
    severe_count = sum(
        1 for measurement in measurements if measurement.severity is DriftSeverity.SEVERE
    )
    if severe_count:
        return DriftSeverity.SEVERE
    moderate_count = sum(
        1 for measurement in measurements if measurement.severity is DriftSeverity.MODERATE
    )
    if moderate_count >= thresholds.severe_measurement_count:
        return DriftSeverity.SEVERE
    if moderate_count:
        return DriftSeverity.MODERATE
    if any(measurement.severity is DriftSeverity.LOW for measurement in measurements):
        return DriftSeverity.LOW
    return DriftSeverity.NONE


def _assessment_quality(
    measurements: Sequence[DriftMeasurement],
    *,
    baseline_window: DriftWindow,
    current_window: DriftWindow,
    checked_at: datetime,
) -> DataQualityStatus:
    issues: list[DataQualityIssue] = [
        *baseline_window.quality.issues,
        *current_window.quality.issues,
    ]
    for measurement in measurements:
        if measurement.severity in {DriftSeverity.NONE, DriftSeverity.LOW}:
            continue
        severity = (
            DataTrustLevel.REJECTED
            if measurement.severity is DriftSeverity.SEVERE
            else DataTrustLevel.DEGRADED
        )
        issues.append(
            DataQualityIssue(
                flag=measurement.kind.value,
                severity=severity,
                reason=f"{measurement.metric_name}: {measurement.reason}",
            )
        )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust = DataTrustLevel.REJECTED
    elif issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=tuple(issues),
        source_ref=f"model_drift:{current_window.model_ref}",
        checked_at=checked_at,
    )


def _downgrade_recommendation(
    model_ref: str,
    measurements: Sequence[DriftMeasurement],
    *,
    severity: DriftSeverity,
    quality: DataQualityStatus,
    source_refs: Mapping[str, str],
) -> DowngradeRecommendation | None:
    downgrade_reasons = tuple(
        measurement.reason
        for measurement in measurements
        if measurement.severity is DriftSeverity.SEVERE
        or measurement.kind
        in {
            DriftKind.PREDICTION_QUALITY,
            DriftKind.CONFIDENCE,
            DriftKind.DATA_QUALITY,
        }
        and measurement.severity is DriftSeverity.MODERATE
    )
    if severity is not DriftSeverity.SEVERE and not any(
        measurement.kind
        in {
            DriftKind.PREDICTION_QUALITY,
            DriftKind.CONFIDENCE,
            DriftKind.DATA_QUALITY,
        }
        and measurement.severity is DriftSeverity.MODERATE
        for measurement in measurements
    ):
        return None
    if not downgrade_reasons and not quality.is_trusted:
        downgrade_reasons = (f"drift assessment quality is {quality.trust_level.value}",)
    return DowngradeRecommendation(
        model_ref=model_ref,
        recommended_status=ModelLifecycleStatus.DEGRADED.value,
        reasons=tuple(dict.fromkeys(downgrade_reasons)),
        manual_review_required=True,
        source_refs=source_refs,
    )


def _retraining_recommendation(
    model_ref: str,
    current: DriftWindow,
    measurements: Sequence[DriftMeasurement],
    *,
    severity: DriftSeverity,
    source_refs: Mapping[str, str],
) -> RetrainingRecommendation:
    reasons = tuple(
        measurement.reason
        for measurement in measurements
        if measurement.kind
        in {
            DriftKind.FEATURE,
            DriftKind.DISTRIBUTION,
            DriftKind.CONCEPT_PROXY,
            DriftKind.PREDICTION_QUALITY,
            DriftKind.CONFIDENCE,
        }
        and measurement.severity in {DriftSeverity.MODERATE, DriftSeverity.SEVERE}
    )
    return RetrainingRecommendation(
        model_ref=model_ref,
        recommended=bool(reasons),
        urgency=severity if reasons else DriftSeverity.NONE,
        reasons=tuple(dict.fromkeys(reasons)),
        suggested_window_ref=f"{current.name}:{current.started_at.isoformat()}:{current.ended_at.isoformat()}",
        source_refs=source_refs,
    )


def _threshold_severity(
    value: Decimal,
    threshold: Decimal,
    thresholds: DriftRuleThresholds,
) -> DriftSeverity:
    if threshold == DECIMAL_ZERO:
        return DriftSeverity.SEVERE if value > DECIMAL_ZERO else DriftSeverity.NONE
    if value >= threshold * thresholds.severe_multiplier:
        return DriftSeverity.SEVERE
    if value >= threshold:
        return DriftSeverity.MODERATE
    if value > DECIMAL_ZERO:
        return DriftSeverity.LOW
    return DriftSeverity.NONE


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, DECIMAL_ZERO) / Decimal(len(values))


def _variance(values: Sequence[Decimal]) -> Decimal:
    average = _mean(values)
    return sum((value - average) ** 2 for value in values) / Decimal(len(values))


def _relative_delta(baseline: Decimal, current: Decimal) -> Decimal:
    denominator = max(abs(baseline), Decimal("0.000001"))
    return abs(current - baseline) / denominator


def _source_refs(
    baseline: DriftWindow, current: DriftWindow, extra_refs: Mapping[str, str]
) -> Mapping[str, str]:
    baseline_ref = (
        f"{baseline.name}:{baseline.started_at.isoformat()}:{baseline.ended_at.isoformat()}"
    )
    current_ref = f"{current.name}:{current.started_at.isoformat()}:{current.ended_at.isoformat()}"
    refs = {
        "baseline_window": baseline_ref,
        "current_window": current_ref,
    }
    refs.update(baseline.source_refs)
    refs.update(current.source_refs)
    refs.update(extra_refs)
    return refs
