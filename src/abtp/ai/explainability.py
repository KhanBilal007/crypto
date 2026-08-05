"""Deterministic prediction explainability contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from abtp.ai.baseline import BaselinePrediction
from abtp.ai.regime import RegimeClassification
from abtp.data import DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.features import FeatureSnapshot


@dataclass(frozen=True, slots=True)
class FeatureContribution:
    """One feature contribution used for prediction explanation."""

    feature_name: str
    value: JsonValue
    weight: Decimal
    direction: str
    rationale: str
    source_ref: str

    def __post_init__(self) -> None:
        if not self.feature_name.strip():
            raise ValueError("feature_name is required")
        if not Decimal("0") <= self.weight <= Decimal("1"):
            raise ValueError("feature contribution weight must be between 0 and 1")
        if not self.direction.strip():
            raise ValueError("feature contribution direction is required")
        if not self.rationale.strip():
            raise ValueError("feature contribution rationale is required")
        if not self.source_ref.strip():
            raise ValueError("feature contribution source_ref is required")


@dataclass(frozen=True, slots=True)
class PredictionExplanation:
    """Auditable explanation for one prediction service result."""

    model_name: str
    model_version: str
    features_ref: str
    summary: str
    feature_importance: tuple[FeatureContribution, ...]
    data_quality_score: Decimal
    source_refs: Mapping[str, str]
    generated_at: datetime
    quality: DataQualityStatus
    regime_label: str | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.model_name, "model_name"),
            (self.model_version, "model_version"),
            (self.features_ref, "features_ref"),
            (self.summary, "summary"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")
        if not Decimal("0") <= self.data_quality_score <= Decimal("1"):
            raise ValueError("data_quality_score must be between 0 and 1")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))

    @property
    def flags(self) -> tuple[str, ...]:
        return self.quality.flags

    def to_json_dict(self) -> Mapping[str, JsonValue]:
        """Return a JSON-compatible explanation snapshot without secrets."""

        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "features_ref": self.features_ref,
            "summary": self.summary,
            "feature_importance": [
                {
                    "feature_name": item.feature_name,
                    "value": item.value,
                    "weight": str(item.weight),
                    "direction": item.direction,
                    "rationale": item.rationale,
                    "source_ref": item.source_ref,
                }
                for item in self.feature_importance
            ],
            "data_quality_score": str(self.data_quality_score),
            "source_refs": dict(self.source_refs),
            "generated_at": self.generated_at.isoformat(),
            "quality": self.quality.trust_level.value,
            "flags": list(self.flags),
            "regime_label": self.regime_label,
            "limitations": list(self.limitations),
        }


def explain_prediction(
    *,
    prediction: BaselinePrediction,
    snapshot: FeatureSnapshot,
    regime: RegimeClassification | None = None,
    top_n: int = 6,
) -> PredictionExplanation:
    """Explain a probability prediction from current/past inputs only."""

    if top_n <= 0:
        raise ValueError("top_n must be positive")
    quality = _explanation_quality(snapshot.quality, regime)
    contributions = _feature_contributions(snapshot, prediction, limit=top_n)
    regime_label = regime.label.value if regime is not None else None
    return PredictionExplanation(
        model_name=prediction.model_metadata.model_name,
        model_version=prediction.model_metadata.version,
        features_ref=prediction.features_ref,
        summary=_summary(prediction, regime),
        feature_importance=contributions,
        data_quality_score=data_quality_score(quality),
        source_refs=_source_refs(snapshot, regime),
        generated_at=prediction.generated_at,
        quality=quality,
        regime_label=regime_label,
        limitations=prediction.model_metadata.limitations,
    )


def data_quality_score(quality: DataQualityStatus) -> Decimal:
    """Convert quality flags into a conservative score for consumers."""

    if quality.is_rejected:
        return Decimal("0")
    if quality.is_degraded:
        penalty = min(Decimal("0.30"), Decimal("0.05") * Decimal(len(quality.issues)))
        return Decimal("0.50") - penalty
    return Decimal("1")


def _feature_contributions(
    snapshot: FeatureSnapshot,
    prediction: BaselinePrediction,
    *,
    limit: int,
) -> tuple[FeatureContribution, ...]:
    candidates: list[FeatureContribution] = []
    for feature_name, weight in _FEATURE_WEIGHTS.items():
        if feature_name not in snapshot.values:
            continue
        value = snapshot.values[feature_name]
        candidates.append(
            FeatureContribution(
                feature_name=feature_name,
                value=str(value),
                weight=weight,
                direction=_direction(feature_name, value, prediction),
                rationale=_rationale(feature_name, value),
                source_ref=snapshot.source_refs.get(feature_name, snapshot.inputs_ref),
            )
        )
    return tuple(sorted(candidates, key=lambda item: item.weight, reverse=True)[:limit])


def _summary(
    prediction: BaselinePrediction,
    regime: RegimeClassification | None,
) -> str:
    direction = prediction.predicted_direction.value
    regime_text = regime.label.value if regime is not None else "not supplied"
    return (
        f"{prediction.model_metadata.model_name} estimates {direction} direction with "
        f"{prediction.confidence} confidence; regime={regime_text}; "
        "output is probability context only."
    )


def _direction(
    feature_name: str,
    value: Decimal,
    prediction: BaselinePrediction,
) -> str:
    if feature_name in {"market.return_1", "market.return_3"}:
        if value > Decimal("0"):
            return "supports_up"
        if value < Decimal("0"):
            return "supports_down"
        return "neutral"
    if feature_name in {"indicator.atr.atr_pct", "liquidity.spread_bps", "data_quality.flag_count"}:
        return "risk_context"
    if prediction.probability_up > prediction.probability_down:
        return "supports_up"
    if prediction.probability_down > prediction.probability_up:
        return "supports_down"
    return "neutral"


def _rationale(feature_name: str, value: Decimal) -> str:
    if feature_name == "market.return_1":
        return "current return nudges the conservative baseline probability"
    if feature_name == "market.return_3":
        return "recent multi-period return describes short-term direction"
    if feature_name == "indicator.atr.atr_pct":
        return "ATR percentage contributes expected volatility and risk context"
    if feature_name == "market.volume_ratio":
        return "volume ratio highlights unusual participation"
    if feature_name == "liquidity.spread_bps":
        return "spread reflects liquidity and execution-risk context"
    if feature_name == "data_quality.flag_count":
        return f"quality flag count is {value}"
    return "feature was included in the prediction input snapshot"


def _explanation_quality(
    feature_quality: DataQualityStatus,
    regime: RegimeClassification | None,
) -> DataQualityStatus:
    issues = [*feature_quality.issues]
    if regime is not None:
        issues.extend(regime.quality.issues)
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif (
        issues or feature_quality.is_degraded or (regime is not None and regime.quality.is_degraded)
    ):
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="prediction_explanation",
        checked_at=feature_quality.checked_at,
    )


def _source_refs(
    snapshot: FeatureSnapshot,
    regime: RegimeClassification | None,
) -> Mapping[str, str]:
    refs = dict(snapshot.source_refs)
    refs["features"] = snapshot.inputs_ref
    if regime is not None:
        refs["regime"] = ",".join(regime.source_refs.values())
    return refs


_FEATURE_WEIGHTS: Mapping[str, Decimal] = {
    "market.return_1": Decimal("0.30"),
    "market.return_3": Decimal("0.20"),
    "indicator.atr.atr_pct": Decimal("0.18"),
    "market.volume_ratio": Decimal("0.12"),
    "liquidity.spread_bps": Decimal("0.10"),
    "data_quality.flag_count": Decimal("0.10"),
}


def feature_names_from_importance(
    contributions: Sequence[FeatureContribution],
) -> tuple[str, ...]:
    """Return stable feature names from explanation contributions."""

    return tuple(item.feature_name for item in contributions)
