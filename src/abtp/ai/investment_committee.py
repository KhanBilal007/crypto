"""Advisory AI investment committee voting."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.ai.vote_models import VoteDirection
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


class CommitteeMember(StrEnum):
    """Stage 060 AI investment committee seats."""

    TREND_AI = "trend_ai"
    MOMENTUM_AI = "momentum_ai"
    MACRO_AI = "macro_ai"
    RISK_AI = "risk_ai"
    ONCHAIN_AI = "onchain_ai"
    FUNDAMENTAL_AI = "fundamental_ai"
    LIQUIDITY_AI = "liquidity_ai"
    SENTIMENT_AI = "sentiment_ai"
    PORTFOLIO_AI = "portfolio_ai"
    EXECUTION_AI = "execution_ai"


class CommitteeRecommendation(StrEnum):
    """Advisory committee recommendation."""

    FAVORABLE_REVIEW = "favorable_review"
    DEFENSIVE_REVIEW = "defensive_review"
    HOLD_REVIEW = "hold_review"
    NO_DECISION = "no_decision"


@dataclass(frozen=True, slots=True)
class InvestmentCommitteePolicy:
    """Conservative Stage 060 committee thresholds."""

    minimum_votes: int = 5
    minimum_confidence: Decimal = Decimal("0.45")
    minimum_agreement_ratio: Decimal = Decimal("0.60")
    maximum_disagreement_ratio: Decimal = Decimal("0.35")
    require_risk_vote: bool = True
    require_portfolio_vote: bool = True
    policy_version: str = "stage-060.v1"

    def __post_init__(self) -> None:
        if self.minimum_votes <= 0:
            raise ValueError("minimum_votes must be positive")
        for name, value in (
            ("minimum_confidence", self.minimum_confidence),
            ("minimum_agreement_ratio", self.minimum_agreement_ratio),
            ("maximum_disagreement_ratio", self.maximum_disagreement_ratio),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class InvestmentCommitteeVote:
    """One advisory committee member vote."""

    member: CommitteeMember
    direction: VoteDirection
    confidence: Decimal
    rationale: str
    inputs_ref: str
    quality: DataQualityStatus
    generated_at: datetime
    weight: Decimal = Decimal("1")
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "member", CommitteeMember(self.member))
        object.__setattr__(self, "direction", VoteDirection(self.direction))
        if not DECIMAL_ZERO <= self.confidence <= DECIMAL_ONE:
            raise ValueError("committee vote confidence must be between 0 and 1")
        if self.weight <= DECIMAL_ZERO:
            raise ValueError("committee vote weight must be positive")
        if not self.rationale.strip():
            raise ValueError("committee vote rationale is required")
        if not self.inputs_ref.strip():
            raise ValueError("committee vote inputs_ref is required")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def weighted_confidence(self) -> Decimal:
        return self.confidence * self.weight

    def as_dict(self) -> dict[str, object]:
        return {
            "member": self.member.value,
            "direction": self.direction.value,
            "confidence": str(self.confidence),
            "weight": str(self.weight),
            "weighted_confidence": str(self.weighted_confidence),
            "rationale": self.rationale,
            "inputs_ref": self.inputs_ref,
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class CommitteeTally:
    """Weighted committee tally and disagreement metrics."""

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
class InvestmentCommitteeReport:
    """Advisory committee report with no trading authority."""

    generated_at: datetime
    recommendation: CommitteeRecommendation
    direction: VoteDirection
    confidence: Decimal
    disagreement: Decimal
    actionable: bool
    tally: CommitteeTally
    votes: tuple[InvestmentCommitteeVote, ...]
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    limitations: tuple[str, ...] = (
        "AI investment committee output is advisory context only.",
        (
            "Committee recommendations cannot create signals, risk decisions, "
            "order intents, or execution."
        ),
        "No model serving, exchange calls, provider calls, or live trading are performed.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by committee voting.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "recommendation", CommitteeRecommendation(self.recommendation))
        object.__setattr__(self, "direction", VoteDirection(self.direction))
        for name, value in (("confidence", self.confidence), ("disagreement", self.disagreement)):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.votes:
            raise ValueError("committee report requires votes")
        if not self.reasons:
            raise ValueError("committee report requires reasons")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("committee limitations are required")

    @property
    def advisory_only(self) -> bool:
        return True

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "recommendation": self.recommendation.value,
            "direction": self.direction.value,
            "confidence": str(self.confidence),
            "disagreement": str(self.disagreement),
            "actionable": self.actionable,
            "tally": self.tally.as_dict(),
            "votes": [vote.as_dict() for vote in self.votes],
            "reasons": list(self.reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "recommendation": self.recommendation.value,
            "direction": self.direction.value,
            "confidence": str(self.confidence),
            "disagreement": str(self.disagreement),
            "actionable": str(self.actionable),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("AI investment committee cannot create signals")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("AI investment committee cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("AI investment committee cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("AI investment committee cannot submit orders")


def evaluate_investment_committee(
    votes: Sequence[InvestmentCommitteeVote],
    *,
    generated_at: datetime | None = None,
    policy: InvestmentCommitteePolicy | None = None,
) -> InvestmentCommitteeReport:
    """Evaluate supplied committee votes without model serving or execution."""

    active_policy = policy or InvestmentCommitteePolicy()
    checked_at = generated_at or _latest_vote_time(votes)
    issues = [issue for vote in votes for issue in vote.quality.issues]
    rejections = _rejection_reasons(votes, active_policy)
    tally = _tally(votes)
    confidence = _confidence(votes, tally)
    if confidence < active_policy.minimum_confidence:
        rejections.append("committee confidence is below threshold")
        issues.append(_issue("low_committee_confidence", DataTrustLevel.REJECTED, rejections[-1]))
    if tally.agreement_ratio < active_policy.minimum_agreement_ratio:
        rejections.append("committee agreement is below threshold")
        issues.append(_issue("low_committee_agreement", DataTrustLevel.REJECTED, rejections[-1]))
    if tally.disagreement_ratio > active_policy.maximum_disagreement_ratio:
        rejections.append("committee disagreement exceeds threshold")
        issues.append(_issue("committee_disagreement", DataTrustLevel.REJECTED, rejections[-1]))
    quality = _quality(votes, issues, bool(rejections), checked_at)
    actionable = not rejections and quality.is_trusted
    direction = tally.winning_direction if actionable else VoteDirection.ABSTAIN
    recommendation = _recommendation(direction, actionable)
    return InvestmentCommitteeReport(
        generated_at=checked_at,
        recommendation=recommendation,
        direction=direction,
        confidence=confidence,
        disagreement=tally.disagreement_ratio.quantize(SCORE_QUANT),
        actionable=actionable,
        tally=tally,
        votes=tuple(votes),
        reasons=_reasons(recommendation, tally, confidence),
        rejection_reasons=tuple(dict.fromkeys(rejections)),
        quality=quality,
        policy_version=active_policy.policy_version,
    )


def deterministic_committee_vote(
    *,
    member: CommitteeMember,
    direction: VoteDirection,
    confidence: Decimal,
    generated_at: datetime,
    rationale: str,
    inputs_ref: str = "fixture:committee",
    weight: Decimal = Decimal("1"),
    quality: DataQualityStatus | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> InvestmentCommitteeVote:
    """Build deterministic committee votes for tests and stored-review pipelines."""

    return InvestmentCommitteeVote(
        member=member,
        direction=direction,
        confidence=confidence,
        generated_at=generated_at,
        rationale=rationale,
        inputs_ref=inputs_ref,
        quality=quality
        or DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref=f"investment_committee:{CommitteeMember(member).value}",
            checked_at=normalize_timestamp(generated_at),
        ),
        weight=weight,
        source_refs=source_refs or {},
    )


def _rejection_reasons(
    votes: Sequence[InvestmentCommitteeVote], policy: InvestmentCommitteePolicy
) -> list[str]:
    reasons: list[str] = []
    if len(votes) < policy.minimum_votes:
        reasons.append("not enough committee votes supplied")
    members = {vote.member for vote in votes}
    if policy.require_risk_vote and CommitteeMember.RISK_AI not in members:
        reasons.append("risk AI vote is required")
    if policy.require_portfolio_vote and CommitteeMember.PORTFOLIO_AI not in members:
        reasons.append("portfolio AI vote is required")
    for vote in votes:
        if vote.quality.is_rejected:
            reasons.append(f"{vote.member.value} vote quality is rejected")
        if vote.direction is VoteDirection.ABSTAIN:
            reasons.append(f"{vote.member.value} abstained")
    return reasons


def _tally(votes: Sequence[InvestmentCommitteeVote]) -> CommitteeTally:
    bullish = _direction_weight(votes, VoteDirection.BULLISH)
    bearish = _direction_weight(votes, VoteDirection.BEARISH)
    neutral = _direction_weight(votes, VoteDirection.NEUTRAL)
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
    return CommitteeTally(
        bullish_weight=bullish.quantize(SCORE_QUANT),
        bearish_weight=bearish.quantize(SCORE_QUANT),
        neutral_weight=neutral.quantize(SCORE_QUANT),
        total_weight=total.quantize(SCORE_QUANT),
        winning_direction=winning,
        agreement_ratio=(winner_weight / total if total > DECIMAL_ZERO else DECIMAL_ZERO).quantize(
            SCORE_QUANT
        ),
        disagreement_ratio=(
            opposing_weight / total if total > DECIMAL_ZERO else DECIMAL_ZERO
        ).quantize(SCORE_QUANT),
    )


def _direction_weight(
    votes: Sequence[InvestmentCommitteeVote], direction: VoteDirection
) -> Decimal:
    return sum(
        (vote.weight * vote.confidence for vote in votes if vote.direction is direction),
        DECIMAL_ZERO,
    )


def _winner(bullish: Decimal, bearish: Decimal, neutral: Decimal) -> VoteDirection:
    ordered = sorted(
        (
            (bullish, VoteDirection.BULLISH),
            (bearish, VoteDirection.BEARISH),
            (neutral, VoteDirection.NEUTRAL),
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if len(ordered) > 1 and ordered[0][0] == ordered[1][0]:
        return VoteDirection.ABSTAIN
    return ordered[0][1] if ordered[0][0] > DECIMAL_ZERO else VoteDirection.ABSTAIN


def _confidence(votes: Sequence[InvestmentCommitteeVote], tally: CommitteeTally) -> Decimal:
    if not votes:
        return DECIMAL_ZERO
    included = [vote.confidence for vote in votes if not vote.quality.is_rejected]
    if not included:
        return DECIMAL_ZERO
    average_confidence = sum(included, DECIMAL_ZERO) / Decimal(len(included))
    confidence = average_confidence * Decimal("0.60") + tally.agreement_ratio * Decimal("0.40")
    if any(vote.quality.is_degraded for vote in votes):
        confidence -= Decimal("0.10")
    if any(vote.quality.is_rejected for vote in votes):
        confidence = min(confidence, Decimal("0.25"))
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, confidence)).quantize(SCORE_QUANT)


def _recommendation(direction: VoteDirection, actionable: bool) -> CommitteeRecommendation:
    if not actionable:
        return CommitteeRecommendation.NO_DECISION
    if direction is VoteDirection.BULLISH:
        return CommitteeRecommendation.FAVORABLE_REVIEW
    if direction is VoteDirection.BEARISH:
        return CommitteeRecommendation.DEFENSIVE_REVIEW
    return CommitteeRecommendation.HOLD_REVIEW


def _quality(
    votes: Sequence[InvestmentCommitteeVote],
    issues: list[DataQualityIssue],
    has_rejections: bool,
    checked_at: datetime,
) -> DataQualityStatus:
    if has_rejections or any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust = DataTrustLevel.REJECTED
    elif issues or any(vote.quality.is_degraded for vote in votes):
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=tuple(issues),
        source_ref="ai:investment_committee:stage-060",
        checked_at=normalize_timestamp(checked_at),
    )


def _reasons(
    recommendation: CommitteeRecommendation, tally: CommitteeTally, confidence: Decimal
) -> tuple[str, ...]:
    return (
        f"committee recommendation is {recommendation.value}",
        f"winning direction is {tally.winning_direction.value}",
        f"agreement ratio is {tally.agreement_ratio}",
        f"disagreement ratio is {tally.disagreement_ratio}",
        f"committee confidence is {confidence}",
    )


def _latest_vote_time(votes: Sequence[InvestmentCommitteeVote]) -> datetime:
    if not votes:
        raise ValueError("committee votes are required")
    return max(vote.generated_at for vote in votes)


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=flag, severity=severity, reason=reason)
