"""Consensus rules for deterministic Multi-AI voting."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from abtp.ai.vote_models import ModelVote, VoteDirection
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp


class VotingMethod(StrEnum):
    """Supported deterministic consensus methods."""

    MAJORITY = "majority"
    WEIGHTED = "weighted"


@dataclass(frozen=True, slots=True)
class VotingPolicy:
    """Fail-closed consensus policy."""

    method: VotingMethod = VotingMethod.WEIGHTED
    minimum_votes: int = 3
    minimum_model_confidence: Decimal = Decimal("0.35")
    minimum_consensus_confidence: Decimal = Decimal("0.45")
    minimum_agreement_ratio: Decimal = Decimal("0.60")
    maximum_disagreement_ratio: Decimal = Decimal("0.40")
    require_trusted_votes: bool = False
    policy_version: str = "stage-036.v1"

    def __post_init__(self) -> None:
        if self.minimum_votes <= 0:
            raise ValueError("minimum_votes must be positive")
        for value, field_name in (
            (self.minimum_model_confidence, "minimum_model_confidence"),
            (self.minimum_consensus_confidence, "minimum_consensus_confidence"),
            (self.minimum_agreement_ratio, "minimum_agreement_ratio"),
            (self.maximum_disagreement_ratio, "maximum_disagreement_ratio"),
        ):
            if not Decimal("0") <= value <= Decimal("1"):
                raise ValueError(f"{field_name} must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class VoteLogEntry:
    """Explainable log for one model vote contribution."""

    model_name: str
    family: str
    direction: VoteDirection
    confidence: Decimal
    weight: Decimal
    included: bool
    reasons: tuple[str, ...]
    inputs_ref: str
    rationale: str

    def as_dict(self) -> dict[str, object]:
        return {
            "model_name": self.model_name,
            "family": self.family,
            "direction": self.direction.value,
            "confidence": str(self.confidence),
            "weight": str(self.weight),
            "included": self.included,
            "reasons": list(self.reasons),
            "inputs_ref": self.inputs_ref,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class ConsensusTally:
    """Weighted vote tally for the winning and opposing sides."""

    bullish_weight: Decimal
    bearish_weight: Decimal
    neutral_weight: Decimal
    total_weight: Decimal
    winning_direction: VoteDirection
    agreement_ratio: Decimal
    disagreement_ratio: Decimal

    def as_dict(self) -> dict[str, str]:
        return {
            "bullish_weight": str(self.bullish_weight),
            "bearish_weight": str(self.bearish_weight),
            "neutral_weight": str(self.neutral_weight),
            "total_weight": str(self.total_weight),
            "winning_direction": self.winning_direction.value,
            "agreement_ratio": str(self.agreement_ratio),
            "disagreement_ratio": str(self.disagreement_ratio),
        }


@dataclass(frozen=True, slots=True)
class ConsensusResult:
    """Advisory consensus result with no trading authority."""

    generated_at: datetime
    direction: VoteDirection
    consensus_score: Decimal
    confidence: Decimal
    actionable: bool
    rejected_reasons: tuple[str, ...]
    quality: DataQualityStatus
    tally: ConsensusTally
    vote_logs: tuple[VoteLogEntry, ...]
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Consensus is advisory strategy context only.",
        "Consensus cannot create orders, order intents, risk decisions, or execution.",
        "All future signals must still pass the Strategy Engine and Risk Management Engine.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def require_actionable(self) -> None:
        """Fail closed when a future consumer asks for actionable context."""

        if not self.actionable:
            raise ValueError("; ".join(self.rejected_reasons))

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "direction": self.direction.value,
            "consensus_score": str(self.consensus_score),
            "confidence": str(self.confidence),
            "actionable": self.actionable,
            "rejected_reasons": list(self.rejected_reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "tally": self.tally.as_dict(),
            "vote_logs": [entry.as_dict() for entry in self.vote_logs],
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }


def build_consensus(
    votes: Sequence[ModelVote],
    *,
    policy: VotingPolicy | None = None,
    generated_at: datetime | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> ConsensusResult:
    """Build deterministic majority or weighted consensus from model votes."""

    active_policy = policy or VotingPolicy()
    checked_at = generated_at or _latest_vote_time(votes) or datetime.now(UTC)
    vote_logs = tuple(_vote_log(vote, active_policy) for vote in votes)
    usable_votes = tuple(vote for vote, log in zip(votes, vote_logs, strict=True) if log.included)
    tally = _tally(usable_votes, active_policy)
    consensus_score = _consensus_score(tally)
    confidence = _consensus_confidence(usable_votes, tally)
    reasons = _rejected_reasons(
        votes=votes,
        usable_votes=usable_votes,
        logs=vote_logs,
        tally=tally,
        confidence=confidence,
        policy=active_policy,
    )
    quality = _quality(votes, reasons, checked_at=checked_at)
    actionable = not reasons and quality.is_trusted
    direction = tally.winning_direction if actionable else VoteDirection.ABSTAIN
    return ConsensusResult(
        generated_at=checked_at,
        direction=direction,
        consensus_score=consensus_score,
        confidence=confidence,
        actionable=actionable,
        rejected_reasons=reasons,
        quality=quality,
        tally=tally,
        vote_logs=vote_logs,
        policy_version=active_policy.policy_version,
        source_refs=source_refs or {},
    )


def _vote_log(vote: ModelVote, policy: VotingPolicy) -> VoteLogEntry:
    reasons: list[str] = []
    if vote.quality.is_rejected:
        reasons.append("model vote quality is rejected")
    if policy.require_trusted_votes and not vote.quality.is_trusted:
        reasons.append("model vote quality is not trusted")
    if vote.confidence < policy.minimum_model_confidence:
        reasons.append("model vote confidence is below threshold")
    if vote.direction is VoteDirection.ABSTAIN:
        reasons.append("model abstained")
    return VoteLogEntry(
        model_name=vote.model_name,
        family=vote.family.value,
        direction=vote.direction,
        confidence=vote.confidence,
        weight=vote.weight,
        included=not reasons,
        reasons=tuple(reasons),
        inputs_ref=vote.inputs_ref,
        rationale=vote.rationale,
    )


def _tally(votes: Sequence[ModelVote], policy: VotingPolicy) -> ConsensusTally:
    bullish = _direction_weight(votes, VoteDirection.BULLISH, policy)
    bearish = _direction_weight(votes, VoteDirection.BEARISH, policy)
    neutral = _direction_weight(votes, VoteDirection.NEUTRAL, policy)
    total = bullish + bearish + neutral
    winning = _winner(bullish, bearish, neutral)
    winner_weight = {
        VoteDirection.BULLISH: bullish,
        VoteDirection.BEARISH: bearish,
        VoteDirection.NEUTRAL: neutral,
        VoteDirection.ABSTAIN: DECIMAL_ZERO,
    }[winning]
    opposing_weight = (
        bearish
        if winning is VoteDirection.BULLISH
        else bullish
        if winning is VoteDirection.BEARISH
        else max(bullish, bearish)
    )
    return ConsensusTally(
        bullish_weight=bullish,
        bearish_weight=bearish,
        neutral_weight=neutral,
        total_weight=total,
        winning_direction=winning,
        agreement_ratio=winner_weight / total if total > DECIMAL_ZERO else DECIMAL_ZERO,
        disagreement_ratio=opposing_weight / total if total > DECIMAL_ZERO else DECIMAL_ZERO,
    )


DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


def _direction_weight(
    votes: Sequence[ModelVote],
    direction: VoteDirection,
    policy: VotingPolicy,
) -> Decimal:
    if policy.method is VotingMethod.MAJORITY:
        return Decimal(sum(1 for vote in votes if vote.direction is direction))
    return sum(
        (vote.weight * vote.confidence for vote in votes if vote.direction is direction),
        DECIMAL_ZERO,
    )


def _winner(
    bullish: Decimal,
    bearish: Decimal,
    neutral: Decimal,
) -> VoteDirection:
    ordered = (
        (VoteDirection.BULLISH, bullish),
        (VoteDirection.BEARISH, bearish),
        (VoteDirection.NEUTRAL, neutral),
    )
    winner, winner_weight = max(ordered, key=lambda item: (item[1], item[0].value))
    tied = sum(1 for _, weight in ordered if weight == winner_weight)
    return VoteDirection.ABSTAIN if tied > 1 or winner_weight == DECIMAL_ZERO else winner


def _consensus_score(tally: ConsensusTally) -> Decimal:
    if tally.total_weight == DECIMAL_ZERO:
        return DECIMAL_ZERO
    return (tally.bullish_weight - tally.bearish_weight) / tally.total_weight


def _consensus_confidence(votes: Sequence[ModelVote], tally: ConsensusTally) -> Decimal:
    if not votes or tally.total_weight == DECIMAL_ZERO:
        return DECIMAL_ZERO
    weighted_average = sum((vote.confidence * vote.weight for vote in votes), DECIMAL_ZERO) / sum(
        (vote.weight for vote in votes), DECIMAL_ZERO
    )
    return min(DECIMAL_ONE, weighted_average * tally.agreement_ratio)


def _rejected_reasons(
    *,
    votes: Sequence[ModelVote],
    usable_votes: Sequence[ModelVote],
    logs: Sequence[VoteLogEntry],
    tally: ConsensusTally,
    confidence: Decimal,
    policy: VotingPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not votes:
        reasons.append("no model votes supplied")
    excluded = tuple(log for log in logs if not log.included)
    if excluded:
        reasons.extend(f"{log.model_name}: {reason}" for log in excluded for reason in log.reasons)
    if len(usable_votes) < policy.minimum_votes:
        reasons.append("insufficient usable model votes")
    if tally.winning_direction is VoteDirection.ABSTAIN:
        reasons.append("no clear consensus direction")
    if tally.agreement_ratio < policy.minimum_agreement_ratio:
        reasons.append("model agreement is below threshold")
    if tally.disagreement_ratio > policy.maximum_disagreement_ratio:
        reasons.append("model disagreement exceeds threshold")
    if confidence < policy.minimum_consensus_confidence:
        reasons.append("consensus confidence is below threshold")
    return tuple(dict.fromkeys(reasons))


def _quality(
    votes: Sequence[ModelVote],
    reasons: tuple[str, ...],
    *,
    checked_at: datetime,
) -> DataQualityStatus:
    issues: list[DataQualityIssue] = []
    for vote in votes:
        issues.extend(vote.quality.issues)
    issues.extend(
        DataQualityIssue(
            flag="non_actionable_consensus",
            severity=DataTrustLevel.DEGRADED,
            reason=reason,
        )
        for reason in reasons
    )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif issues:
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="ai_voting:consensus",
        checked_at=normalize_timestamp(checked_at),
    )


def _latest_vote_time(votes: Sequence[ModelVote]) -> datetime | None:
    if not votes:
        return None
    return max(vote.generated_at for vote in votes)
