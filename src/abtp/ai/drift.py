"""Model drift detection contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityStatus, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.features import FeatureSnapshot

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


class DriftKind(StrEnum):
    """Families of model drift and degradation checks."""

    FEATURE = "feature_drift"
    DISTRIBUTION = "distribution_drift"
    CONCEPT_PROXY = "concept_drift_proxy"
    PREDICTION_QUALITY = "prediction_quality_degradation"
    CONFIDENCE = "confidence_degradation"
    DATA_QUALITY = "data_quality"


class DriftSeverity(StrEnum):
    """Fail-safe severity labels for drift measurements."""

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    SEVERE = "severe"


@dataclass(frozen=True, slots=True)
class DriftWindow:
    """Feature, prediction, and outcome window used by drift checks."""

    model_ref: str
    name: str
    started_at: datetime
    ended_at: datetime
    feature_values: Mapping[str, tuple[Decimal, ...]]
    quality: DataQualityStatus
    prediction_confidences: tuple[Decimal, ...] = ()
    outcome_accuracy: Decimal | None = None
    directional_hit_rate: Decimal | None = None
    calibration_error: Decimal | None = None
    label_distribution: Mapping[str, Decimal] = field(default_factory=dict)
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_ref.strip():
            raise ValueError("model_ref is required")
        if not self.name.strip():
            raise ValueError("drift window name is required")
        object.__setattr__(self, "started_at", normalize_timestamp(self.started_at))
        object.__setattr__(self, "ended_at", normalize_timestamp(self.ended_at))
        if self.ended_at < self.started_at:
            raise ValueError("drift window ended_at cannot be before started_at")
        if not self.feature_values:
            raise ValueError("drift window feature_values are required")
        values: dict[str, tuple[Decimal, ...]] = {}
        for feature_name, feature_series in self.feature_values.items():
            if not feature_name.strip():
                raise ValueError("feature names are required")
            if not feature_series:
                raise ValueError(f"feature series is empty: {feature_name}")
            if any(not value.is_finite() for value in feature_series):
                raise ValueError(f"feature series contains non-finite value: {feature_name}")
            values[feature_name] = tuple(feature_series)
        for confidence in self.prediction_confidences:
            if not DECIMAL_ZERO <= confidence <= DECIMAL_ONE:
                raise ValueError("prediction confidences must be between 0 and 1")
        for name, value in (
            ("outcome_accuracy", self.outcome_accuracy),
            ("directional_hit_rate", self.directional_hit_rate),
            ("calibration_error", self.calibration_error),
        ):
            if value is not None and not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        for label, share in self.label_distribution.items():
            if not label.strip():
                raise ValueError("label names are required")
            if not DECIMAL_ZERO <= share <= DECIMAL_ONE:
                raise ValueError("label distribution shares must be between 0 and 1")
        object.__setattr__(self, "feature_values", values)
        object.__setattr__(self, "label_distribution", dict(self.label_distribution))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def sample_count(self) -> int:
        return min(len(values) for values in self.feature_values.values())

    @property
    def average_confidence(self) -> Decimal | None:
        if not self.prediction_confidences:
            return None
        return sum(self.prediction_confidences, DECIMAL_ZERO) / Decimal(
            len(self.prediction_confidences)
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "model_ref": self.model_ref,
            "name": self.name,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "sample_count": self.sample_count,
            "feature_names": sorted(self.feature_values),
            "prediction_confidence_count": len(self.prediction_confidences),
            "average_confidence": str(self.average_confidence)
            if self.average_confidence is not None
            else None,
            "outcome_accuracy": str(self.outcome_accuracy)
            if self.outcome_accuracy is not None
            else None,
            "directional_hit_rate": str(self.directional_hit_rate)
            if self.directional_hit_rate is not None
            else None,
            "calibration_error": str(self.calibration_error)
            if self.calibration_error is not None
            else None,
            "label_distribution": {
                label: str(share) for label, share in self.label_distribution.items()
            },
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class DriftMeasurement:
    """One explainable drift or degradation measurement."""

    kind: DriftKind
    metric_name: str
    baseline_value: Decimal | None
    current_value: Decimal | None
    delta: Decimal | None
    threshold: Decimal
    severity: DriftSeverity
    reason: str
    evidence: tuple[str, ...]
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.metric_name.strip():
            raise ValueError("drift metric_name is required")
        if self.threshold < DECIMAL_ZERO:
            raise ValueError("drift threshold cannot be negative")
        if not self.reason.strip():
            raise ValueError("drift measurement reason is required")
        if not self.evidence:
            raise ValueError("drift measurement requires evidence")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def is_actionable(self) -> bool:
        return self.severity in {DriftSeverity.MODERATE, DriftSeverity.SEVERE}

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "metric_name": self.metric_name,
            "baseline_value": str(self.baseline_value) if self.baseline_value is not None else None,
            "current_value": str(self.current_value) if self.current_value is not None else None,
            "delta": str(self.delta) if self.delta is not None else None,
            "threshold": str(self.threshold),
            "severity": self.severity.value,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class DowngradeRecommendation:
    """Advisory model-manager downgrade context."""

    model_ref: str
    recommended_status: str
    reasons: tuple[str, ...]
    manual_review_required: bool
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_ref.strip():
            raise ValueError("model_ref is required")
        if not self.recommended_status.strip():
            raise ValueError("recommended_status is required")
        if not self.reasons:
            raise ValueError("downgrade recommendation requires reasons")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "model_ref": self.model_ref,
            "recommended_status": self.recommended_status,
            "reasons": list(self.reasons),
            "manual_review_required": self.manual_review_required,
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class RetrainingRecommendation:
    """Advisory retraining context without starting training."""

    model_ref: str
    recommended: bool
    urgency: DriftSeverity
    reasons: tuple[str, ...]
    suggested_window_ref: str
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_ref.strip():
            raise ValueError("model_ref is required")
        if self.recommended and not self.reasons:
            raise ValueError("retraining recommendation requires reasons")
        if not self.suggested_window_ref.strip():
            raise ValueError("suggested_window_ref is required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "model_ref": self.model_ref,
            "recommended": self.recommended,
            "urgency": self.urgency.value,
            "reasons": list(self.reasons),
            "suggested_window_ref": self.suggested_window_ref,
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class DriftAssessment:
    """Aggregate model drift result consumed by future model-management stages."""

    model_ref: str
    generated_at: datetime
    baseline_window: DriftWindow
    current_window: DriftWindow
    measurements: tuple[DriftMeasurement, ...]
    severity: DriftSeverity
    quality: DataQualityStatus
    downgrade: DowngradeRecommendation | None
    retraining: RetrainingRecommendation
    non_actionable: bool
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_ref.strip():
            raise ValueError("model_ref is required")
        if self.baseline_window.model_ref != self.model_ref:
            raise ValueError("baseline window model_ref must match assessment model_ref")
        if self.current_window.model_ref != self.model_ref:
            raise ValueError("current window model_ref must match assessment model_ref")
        if not self.measurements:
            raise ValueError("drift assessment requires measurements")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def downgrade_recommended(self) -> bool:
        return self.downgrade is not None

    @property
    def retraining_recommended(self) -> bool:
        return self.retraining.recommended

    def as_dict(self) -> dict[str, object]:
        return {
            "model_ref": self.model_ref,
            "generated_at": self.generated_at.isoformat(),
            "baseline_window": self.baseline_window.as_dict(),
            "current_window": self.current_window.as_dict(),
            "measurements": [measurement.as_dict() for measurement in self.measurements],
            "severity": self.severity.value,
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "downgrade": self.downgrade.as_dict() if self.downgrade is not None else None,
            "retraining": self.retraining.as_dict(),
            "non_actionable": self.non_actionable,
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "model_ref": self.model_ref,
            "severity": self.severity.value,
            "measurement_count": str(len(self.measurements)),
            "downgrade_recommended": str(self.downgrade_recommended),
            "retraining_recommended": str(self.retraining_recommended),
            "non_actionable": str(self.non_actionable),
            "quality": self.quality.trust_level.value,
            "quality_flags": "|".join(self.quality.flags),
            "policy_version": self.policy_version,
        }


def drift_window_from_feature_snapshots(
    *,
    model_ref: str,
    name: str,
    snapshots: Sequence[FeatureSnapshot],
    feature_names: Sequence[str] | None = None,
    prediction_confidences: Sequence[Decimal] = (),
    outcome_accuracy: Decimal | None = None,
    directional_hit_rate: Decimal | None = None,
    calibration_error: Decimal | None = None,
    label_distribution: Mapping[str, Decimal] | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> DriftWindow:
    """Build a drift window from feature snapshots without model inference."""

    if not snapshots:
        raise ValueError("feature snapshots are required")
    selected_names = tuple(feature_names or sorted(snapshots[0].values))
    feature_values: dict[str, list[Decimal]] = {feature_name: [] for feature_name in selected_names}
    for snapshot in snapshots:
        for feature_name in selected_names:
            if feature_name in snapshot.values:
                feature_values[feature_name].append(snapshot.values[feature_name])
    missing = [name for name, values in feature_values.items() if not values]
    if missing:
        raise ValueError(f"feature snapshots are missing selected features: {', '.join(missing)}")
    quality = _combined_snapshot_quality(snapshots, model_ref=model_ref)
    refs = dict(source_refs or {})
    refs.setdefault("features", "|".join(snapshot.inputs_ref for snapshot in snapshots))
    return DriftWindow(
        model_ref=model_ref,
        name=name,
        started_at=min(snapshot.generated_at for snapshot in snapshots),
        ended_at=max(snapshot.generated_at for snapshot in snapshots),
        feature_values={key: tuple(values) for key, values in feature_values.items()},
        quality=quality,
        prediction_confidences=tuple(prediction_confidences),
        outcome_accuracy=outcome_accuracy,
        directional_hit_rate=directional_hit_rate,
        calibration_error=calibration_error,
        label_distribution=label_distribution or {},
        source_refs=refs,
    )


def _combined_snapshot_quality(
    snapshots: Sequence[FeatureSnapshot], *, model_ref: str
) -> DataQualityStatus:
    from abtp.data import DataTrustLevel

    issues = tuple(issue for snapshot in snapshots for issue in snapshot.quality.issues)
    if any(snapshot.quality.is_rejected for snapshot in snapshots):
        trust_level = DataTrustLevel.REJECTED
    elif any(snapshot.quality.is_degraded for snapshot in snapshots):
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=issues,
        source_ref=f"drift_window:{model_ref}",
        checked_at=max(snapshot.generated_at for snapshot in snapshots),
    )
