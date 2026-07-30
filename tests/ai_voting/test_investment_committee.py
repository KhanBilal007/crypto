from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.ai import (
    CommitteeMember,
    CommitteeRecommendation,
    InvestmentCommitteePolicy,
    VoteDirection,
    deterministic_committee_vote,
    evaluate_investment_committee,
)
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_committee_favorable_review_is_explainable_and_actionable_context() -> None:
    report = evaluate_investment_committee(_bullish_committee_votes(), generated_at=NOW)

    assert report.recommendation is CommitteeRecommendation.FAVORABLE_REVIEW
    assert report.direction is VoteDirection.BULLISH
    assert report.actionable
    assert report.confidence == Decimal("0.7104")
    assert report.disagreement == Decimal("0.0000")
    assert report.quality.is_trusted
    assert len(report.votes) == 10
    assert report.audit_payload()["recommendation"] == "favorable_review"


def test_committee_defensive_review_for_bearish_majority() -> None:
    report = evaluate_investment_committee(_bearish_committee_votes(), generated_at=NOW)

    assert report.recommendation is CommitteeRecommendation.DEFENSIVE_REVIEW
    assert report.direction is VoteDirection.BEARISH
    assert report.actionable
    assert report.tally.bearish_weight > report.tally.bullish_weight


def test_committee_disagreement_fails_closed() -> None:
    report = evaluate_investment_committee(
        _split_committee_votes(),
        generated_at=NOW,
        policy=InvestmentCommitteePolicy(maximum_disagreement_ratio=Decimal("0.30")),
    )

    assert report.recommendation is CommitteeRecommendation.NO_DECISION
    assert report.direction is VoteDirection.ABSTAIN
    assert not report.actionable
    assert report.quality.is_rejected
    assert "committee disagreement exceeds threshold" in report.rejection_reasons


def test_missing_required_committee_members_fail_closed() -> None:
    report = evaluate_investment_committee(
        tuple(
            vote
            for vote in _bullish_committee_votes()
            if vote.member is not CommitteeMember.RISK_AI
        ),
        generated_at=NOW,
    )

    assert report.recommendation is CommitteeRecommendation.NO_DECISION
    assert not report.actionable
    assert "risk AI vote is required" in report.rejection_reasons


def test_rejected_committee_vote_fails_closed() -> None:
    votes = (
        *_bullish_committee_votes()[:-1],
        _vote(
            CommitteeMember.EXECUTION_AI,
            VoteDirection.BULLISH,
            Decimal("0.75"),
            quality=_rejected_quality(),
        ),
    )
    report = evaluate_investment_committee(votes, generated_at=NOW)

    assert report.recommendation is CommitteeRecommendation.NO_DECISION
    assert not report.actionable
    assert report.quality.is_rejected
    assert "execution_ai vote quality is rejected" in report.rejection_reasons


def test_degraded_committee_vote_reduces_confidence_and_quality() -> None:
    votes = (
        *_bullish_committee_votes()[:-1],
        _vote(
            CommitteeMember.EXECUTION_AI,
            VoteDirection.BULLISH,
            Decimal("0.75"),
            quality=_degraded_quality(),
        ),
    )
    report = evaluate_investment_committee(votes, generated_at=NOW)

    assert report.recommendation is CommitteeRecommendation.NO_DECISION
    assert not report.actionable
    assert report.quality.is_degraded
    assert report.confidence == Decimal("0.6104")


def test_committee_vote_validates_confidence() -> None:
    with pytest.raises(ValueError, match="committee vote confidence"):
        _vote(CommitteeMember.TREND_AI, VoteDirection.BULLISH, Decimal("1.10"))


def test_committee_report_has_no_trading_authority() -> None:
    report = evaluate_investment_committee(_bullish_committee_votes(), generated_at=NOW)

    with pytest.raises(ValueError, match="cannot create signals"):
        report.create_signal()
    with pytest.raises(ValueError, match="cannot create order intents"):
        report.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()


def test_public_imports_are_available() -> None:
    from abtp.ai import InvestmentCommitteeReport, InvestmentCommitteeVote

    assert InvestmentCommitteeReport is not None
    assert InvestmentCommitteeVote is not None


def _bullish_committee_votes():
    return (
        _vote(
            CommitteeMember.TREND_AI, VoteDirection.BULLISH, Decimal("0.82"), weight=Decimal("1.2")
        ),
        _vote(CommitteeMember.MOMENTUM_AI, VoteDirection.BULLISH, Decimal("0.76")),
        _vote(CommitteeMember.MACRO_AI, VoteDirection.NEUTRAL, Decimal("0.60")),
        _vote(
            CommitteeMember.RISK_AI, VoteDirection.NEUTRAL, Decimal("0.68"), weight=Decimal("1.2")
        ),
        _vote(CommitteeMember.ONCHAIN_AI, VoteDirection.BULLISH, Decimal("0.74")),
        _vote(CommitteeMember.FUNDAMENTAL_AI, VoteDirection.BULLISH, Decimal("0.78")),
        _vote(CommitteeMember.LIQUIDITY_AI, VoteDirection.BULLISH, Decimal("0.70")),
        _vote(CommitteeMember.SENTIMENT_AI, VoteDirection.BULLISH, Decimal("0.62")),
        _vote(
            CommitteeMember.PORTFOLIO_AI,
            VoteDirection.NEUTRAL,
            Decimal("0.72"),
            weight=Decimal("1.2"),
        ),
        _vote(CommitteeMember.EXECUTION_AI, VoteDirection.BULLISH, Decimal("0.75")),
    )


def _bearish_committee_votes():
    return tuple(
        _vote(member, VoteDirection.BEARISH, Decimal("0.74"))
        if member
        in {
            CommitteeMember.TREND_AI,
            CommitteeMember.MOMENTUM_AI,
            CommitteeMember.MACRO_AI,
            CommitteeMember.RISK_AI,
            CommitteeMember.LIQUIDITY_AI,
            CommitteeMember.PORTFOLIO_AI,
        }
        else _vote(member, VoteDirection.NEUTRAL, Decimal("0.58"))
        for member in CommitteeMember
    )


def _split_committee_votes():
    return (
        _vote(CommitteeMember.TREND_AI, VoteDirection.BULLISH, Decimal("0.80")),
        _vote(CommitteeMember.MOMENTUM_AI, VoteDirection.BULLISH, Decimal("0.76")),
        _vote(CommitteeMember.MACRO_AI, VoteDirection.BEARISH, Decimal("0.78")),
        _vote(CommitteeMember.RISK_AI, VoteDirection.BEARISH, Decimal("0.80")),
        _vote(CommitteeMember.ONCHAIN_AI, VoteDirection.BULLISH, Decimal("0.70")),
        _vote(CommitteeMember.FUNDAMENTAL_AI, VoteDirection.BULLISH, Decimal("0.72")),
        _vote(CommitteeMember.LIQUIDITY_AI, VoteDirection.BEARISH, Decimal("0.74")),
        _vote(CommitteeMember.SENTIMENT_AI, VoteDirection.BULLISH, Decimal("0.60")),
        _vote(CommitteeMember.PORTFOLIO_AI, VoteDirection.BEARISH, Decimal("0.76")),
        _vote(CommitteeMember.EXECUTION_AI, VoteDirection.NEUTRAL, Decimal("0.62")),
    )


def _vote(
    member: CommitteeMember,
    direction: VoteDirection,
    confidence: Decimal,
    *,
    weight: Decimal = Decimal("1"),
    quality: DataQualityStatus | None = None,
):
    return deterministic_committee_vote(
        member=member,
        direction=direction,
        confidence=confidence,
        generated_at=NOW,
        rationale=f"{member.value} fixture vote",
        inputs_ref=f"fixture:committee:{member.value}",
        weight=weight,
        quality=quality,
    )


def _degraded_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.DEGRADED,
        issues=(
            DataQualityIssue(
                flag="degraded_committee_vote",
                severity=DataTrustLevel.DEGRADED,
                reason="committee fixture vote is degraded",
            ),
        ),
        source_ref="fixture:committee:degraded",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_committee_vote",
                severity=DataTrustLevel.REJECTED,
                reason="committee fixture vote is rejected",
            ),
        ),
        source_ref="fixture:committee:rejected",
        checked_at=NOW,
    )
