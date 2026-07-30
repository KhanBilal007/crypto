"""Market regime classifier contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from abtp.context import ContextBatch
from abtp.data import DataQualityStatus, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.features import FeatureSnapshot

if TYPE_CHECKING:
    from abtp.ai.regime_rules import RegimeRuleThresholds


class MarketRegimeLabel(StrEnum):
    """Market condition labels consumed by future strategy and risk modules."""

    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    SHOCK = "shock"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RiskAdjustmentSuggestion:
    """Advisory sizing and entry-risk context for later risk controls."""

    max_position_multiplier: Decimal
    block_new_entries: bool
    tighten_stops: bool
    reduce_trade_frequency: bool
    rationale: str

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.max_position_multiplier <= Decimal("1"):
            raise ValueError("max_position_multiplier must be between 0 and 1")
        if not self.rationale.strip():
            raise ValueError("risk adjustment rationale is required")


@dataclass(frozen=True, slots=True)
class RegimeEvidence:
    """One explainable input that influenced a regime decision."""

    key: str
    value: JsonValue
    reason: str
    source_ref: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.key, "evidence key"),
            (self.reason, "evidence reason"),
            (self.source_ref, "evidence source_ref"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")


@dataclass(frozen=True, slots=True)
class RegimeClassification:
    """Regime label, confidence, quality, evidence, and risk adjustment."""

    label: MarketRegimeLabel
    confidence: Decimal
    risk_adjustment: RiskAdjustmentSuggestion
    reasons: tuple[str, ...]
    evidence: tuple[RegimeEvidence, ...]
    source_refs: Mapping[str, str]
    feature_schema_version: str
    generated_at: datetime
    quality: DataQualityStatus

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("regime confidence must be between 0 and 1")
        if not self.reasons:
            raise ValueError("regime classification requires reasons")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))

    @property
    def flags(self) -> tuple[str, ...]:
        return self.quality.flags

    @property
    def is_trusted(self) -> bool:
        return self.quality.is_trusted

    @property
    def is_degraded(self) -> bool:
        return self.quality.is_degraded

    @property
    def is_rejected(self) -> bool:
        return self.quality.is_rejected

    @property
    def is_actionable_context(self) -> bool:
        """Whether future modules may consider this as non-blocking context."""

        return self.quality.is_trusted and not self.risk_adjustment.block_new_entries


class MarketRegimeClassifier:
    """Thin facade over deterministic Stage 018 regime rules."""

    def __init__(self, thresholds: RegimeRuleThresholds | None = None) -> None:
        from abtp.ai.regime_rules import RegimeRuleThresholds

        self._thresholds = thresholds or RegimeRuleThresholds()

    def classify(
        self,
        snapshot: FeatureSnapshot,
        *,
        context_batches: Sequence[ContextBatch] = (),
    ) -> RegimeClassification:
        from abtp.ai.regime_rules import classify_market_regime

        return classify_market_regime(
            snapshot,
            context_batches=context_batches,
            thresholds=self._thresholds,
        )


def unknown_regime(
    *,
    snapshot: FeatureSnapshot,
    confidence: Decimal,
    reasons: tuple[str, ...],
    evidence: tuple[RegimeEvidence, ...],
    quality: DataQualityStatus,
    source_refs: Mapping[str, str],
) -> RegimeClassification:
    """Construct a conservative unknown regime classification."""

    return RegimeClassification(
        label=MarketRegimeLabel.UNKNOWN,
        confidence=confidence,
        risk_adjustment=RiskAdjustmentSuggestion(
            max_position_multiplier=Decimal("0"),
            block_new_entries=True,
            tighten_stops=True,
            reduce_trade_frequency=True,
            rationale="unknown regime is non-actionable until required inputs are trusted",
        ),
        reasons=reasons,
        evidence=evidence,
        source_refs=source_refs,
        feature_schema_version=snapshot.schema_version,
        generated_at=snapshot.generated_at,
        quality=quality,
    )
