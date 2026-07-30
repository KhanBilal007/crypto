"""Read-only model drift reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from abtp.ai.drift import DriftAssessment
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue


@dataclass(frozen=True, slots=True)
class ModelDriftReport:
    """Aggregate drift report for one or more model versions."""

    generated_at: datetime
    assessments: tuple[DriftAssessment, ...]
    quality: DataQualityStatus
    downgrade_recommendations: tuple[str, ...]
    retraining_recommendations: tuple[str, ...]
    non_actionable_models: tuple[str, ...]
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Model drift reports are advisory evidence only.",
        "The report does not retrain, retire, serve, select, or swap models.",
        "Downgrade and retraining recommendations require later approval gates.",
        "No profit is guaranteed by model drift detection.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if not self.assessments:
            raise ValueError("model drift report requires at least one assessment")
        if not self.limitations:
            raise ValueError("model drift report limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "assessments": [assessment.as_dict() for assessment in self.assessments],
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "downgrade_recommendations": list(self.downgrade_recommendations),
            "retraining_recommendations": list(self.retraining_recommendations),
            "non_actionable_models": list(self.non_actionable_models),
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "assessment_count": str(len(self.assessments)),
            "model_refs": "|".join(assessment.model_ref for assessment in self.assessments),
            "downgrade_recommendations": "|".join(self.downgrade_recommendations),
            "retraining_recommendations": "|".join(self.retraining_recommendations),
            "non_actionable_models": "|".join(self.non_actionable_models),
            "quality": self.quality.trust_level.value,
            "quality_flags": "|".join(self.quality.flags),
        }

    def train_model(self, *_args: object, **_kwargs: object) -> None:
        """Reject retraining authority; this report only recommends review."""

        raise ValueError("model drift report cannot train models")

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        """Reject strategy authority."""

        raise ValueError("model drift report cannot create strategy signals")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject execution authority."""

        raise ValueError("model drift report cannot submit orders")


def build_model_drift_report(
    assessments: Sequence[DriftAssessment],
    *,
    generated_at: datetime,
    source_refs: Mapping[str, str] | None = None,
) -> ModelDriftReport:
    """Build a deterministic drift report without changing model state."""

    if not assessments:
        raise ValueError("at least one drift assessment is required")
    checked_at = normalize_timestamp(generated_at)
    report_quality = _report_quality(assessments, checked_at)
    downgrade_recommendations = tuple(
        assessment.model_ref for assessment in assessments if assessment.downgrade_recommended
    )
    retraining_recommendations = tuple(
        assessment.model_ref for assessment in assessments if assessment.retraining_recommended
    )
    non_actionable_models = tuple(
        assessment.model_ref for assessment in assessments if assessment.non_actionable
    )
    return ModelDriftReport(
        generated_at=checked_at,
        assessments=tuple(assessments),
        quality=report_quality,
        downgrade_recommendations=tuple(dict.fromkeys(downgrade_recommendations)),
        retraining_recommendations=tuple(dict.fromkeys(retraining_recommendations)),
        non_actionable_models=tuple(dict.fromkeys(non_actionable_models)),
        source_refs=source_refs or {},
    )


def _report_quality(
    assessments: Sequence[DriftAssessment], checked_at: datetime
) -> DataQualityStatus:
    issues: list[DataQualityIssue] = []
    for assessment in assessments:
        issues.extend(assessment.quality.issues)
        if assessment.downgrade_recommended:
            issues.append(
                DataQualityIssue(
                    flag="model_downgrade_recommended",
                    severity=DataTrustLevel.REJECTED,
                    reason=f"{assessment.model_ref} has a downgrade recommendation",
                )
            )
        elif assessment.retraining_recommended:
            issues.append(
                DataQualityIssue(
                    flag="model_retraining_recommended",
                    severity=DataTrustLevel.DEGRADED,
                    reason=f"{assessment.model_ref} has a retraining recommendation",
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
        source_ref="model_drift:report",
        checked_at=checked_at,
    )
