"""Model vote contracts for the Multi-AI Voting System."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp


class AIVoteFamily(StrEnum):
    """Independent model families used by Stage 036 voting."""

    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    ORDER_BOOK = "order_book"
    ON_CHAIN = "on_chain"
    SENTIMENT = "sentiment"


class VoteDirection(StrEnum):
    """Advisory model direction without signal or order authority."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    ABSTAIN = "abstain"

    @property
    def score(self) -> Decimal:
        if self is VoteDirection.BULLISH:
            return Decimal("1")
        if self is VoteDirection.BEARISH:
            return Decimal("-1")
        return Decimal("0")


LOW_TRUST_OPTIONAL_FAMILIES = frozenset(
    {
        AIVoteFamily.ON_CHAIN,
        AIVoteFamily.SENTIMENT,
    }
)


@dataclass(frozen=True, slots=True)
class ModelVote:
    """One model family's advisory vote and evidence."""

    model_name: str
    family: AIVoteFamily
    direction: VoteDirection
    confidence: Decimal
    generated_at: datetime
    rationale: str
    inputs_ref: str
    quality: DataQualityStatus
    weight: Decimal = Decimal("1")
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name is required")
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("vote confidence must be between 0 and 1")
        if self.weight <= Decimal("0"):
            raise ValueError("vote weight must be positive")
        if not self.rationale.strip():
            raise ValueError("vote rationale is required")
        if not self.inputs_ref.strip():
            raise ValueError("vote inputs_ref is required")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def is_rejected(self) -> bool:
        return self.quality.is_rejected

    @property
    def is_degraded(self) -> bool:
        return self.quality.is_degraded

    @property
    def weighted_confidence(self) -> Decimal:
        return self.weight * self.confidence

    def explain(self) -> dict[str, object]:
        """Return a deterministic vote log row."""

        return {
            "model_name": self.model_name,
            "family": self.family.value,
            "direction": self.direction.value,
            "confidence": str(self.confidence),
            "weight": str(self.weight),
            "weighted_confidence": str(self.weighted_confidence),
            "quality": self.quality.trust_level.value,
            "flags": list(self.quality.flags),
            "inputs_ref": self.inputs_ref,
            "rationale": self.rationale,
            "source_refs": dict(self.source_refs),
        }


def deterministic_model_vote(
    *,
    model_name: str,
    family: AIVoteFamily,
    direction: VoteDirection,
    confidence: Decimal,
    generated_at: datetime,
    inputs_ref: str,
    rationale: str,
    weight: Decimal = Decimal("1"),
    source_refs: Mapping[str, str] | None = None,
    deterministic_source_quality: bool = True,
) -> ModelVote:
    """Build a deterministic fixture/stub vote with conservative quality defaults."""

    quality = _default_quality(
        family=family,
        deterministic_source_quality=deterministic_source_quality,
        checked_at=generated_at,
    )
    return ModelVote(
        model_name=model_name,
        family=family,
        direction=direction,
        confidence=confidence,
        generated_at=generated_at,
        rationale=rationale,
        inputs_ref=inputs_ref,
        quality=quality,
        weight=weight,
        source_refs=source_refs or {},
    )


def _default_quality(
    *,
    family: AIVoteFamily,
    deterministic_source_quality: bool,
    checked_at: datetime,
) -> DataQualityStatus:
    if family in LOW_TRUST_OPTIONAL_FAMILIES and not deterministic_source_quality:
        issue = DataQualityIssue(
            flag="optional_low_trust_model",
            severity=DataTrustLevel.DEGRADED,
            reason=f"{family.value} model source quality is optional or not deterministic",
        )
        return DataQualityStatus(
            trust_level=DataTrustLevel.DEGRADED,
            issues=(issue,),
            source_ref=f"ai_vote:{family.value}",
            checked_at=normalize_timestamp(checked_at),
        )
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref=f"ai_vote:{family.value}",
        checked_at=normalize_timestamp(checked_at),
    )


def rejected_model_vote(
    *,
    model_name: str,
    family: AIVoteFamily,
    direction: VoteDirection,
    confidence: Decimal,
    generated_at: datetime = datetime(2026, 1, 1, tzinfo=UTC),
    reason: str = "model vote fixture rejected",
) -> ModelVote:
    """Build a rejected deterministic vote for fail-closed tests."""

    quality = DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_model_vote",
                severity=DataTrustLevel.REJECTED,
                reason=reason,
            ),
        ),
        source_ref=f"ai_vote:{family.value}:rejected",
        checked_at=normalize_timestamp(generated_at),
    )
    return ModelVote(
        model_name=model_name,
        family=family,
        direction=direction,
        confidence=confidence,
        generated_at=generated_at,
        rationale=reason,
        inputs_ref="fixture:rejected",
        quality=quality,
    )
