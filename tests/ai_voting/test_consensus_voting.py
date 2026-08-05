from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.ai import (
    AIVoteFamily,
    VoteDirection,
    VotingMethod,
    VotingPolicy,
    build_consensus,
    deterministic_model_vote,
    rejected_model_vote,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_weighted_consensus_is_actionable_with_explainable_vote_logs() -> None:
    result = build_consensus(
        (
            _vote("trend", AIVoteFamily.TREND, VoteDirection.BULLISH, "0.80", weight="2"),
            _vote("momentum", AIVoteFamily.MOMENTUM, VoteDirection.BULLISH, "0.70"),
            _vote("volatility", AIVoteFamily.VOLATILITY, VoteDirection.NEUTRAL, "0.50"),
            _vote("orderbook", AIVoteFamily.ORDER_BOOK, VoteDirection.BULLISH, "0.65"),
        ),
        generated_at=NOW,
    )

    assert result.actionable
    assert result.direction is VoteDirection.BULLISH
    assert result.consensus_score > Decimal("0")
    assert result.confidence >= Decimal("0.45")
    assert result.rejected_reasons == ()
    assert result.quality.is_trusted
    assert result.vote_logs[0].included
    assert result.vote_logs[0].inputs_ref == "fixture:features"
    assert result.as_dict()["direction"] == "bullish"


def test_disagreement_and_low_confidence_make_consensus_non_actionable() -> None:
    result = build_consensus(
        (
            _vote("trend", AIVoteFamily.TREND, VoteDirection.BULLISH, "0.80"),
            _vote("momentum", AIVoteFamily.MOMENTUM, VoteDirection.BEARISH, "0.75"),
            _vote("volatility", AIVoteFamily.VOLATILITY, VoteDirection.BEARISH, "0.36"),
        ),
        policy=VotingPolicy(maximum_disagreement_ratio=Decimal("0.30")),
        generated_at=NOW,
    )

    assert not result.actionable
    assert result.direction is VoteDirection.ABSTAIN
    assert "model disagreement exceeds threshold" in result.rejected_reasons
    assert result.quality.is_degraded
    with pytest.raises(ValueError, match="model disagreement"):
        result.require_actionable()


def test_rejected_model_vote_fails_closed() -> None:
    result = build_consensus(
        (
            _vote("trend", AIVoteFamily.TREND, VoteDirection.BULLISH, "0.80"),
            rejected_model_vote(
                model_name="bad-sentiment",
                family=AIVoteFamily.SENTIMENT,
                direction=VoteDirection.BULLISH,
                confidence=Decimal("0.90"),
                generated_at=NOW,
            ),
            _vote("momentum", AIVoteFamily.MOMENTUM, VoteDirection.BULLISH, "0.70"),
        ),
        generated_at=NOW,
    )

    assert not result.actionable
    assert result.quality.is_rejected
    assert any("bad-sentiment" in reason for reason in result.rejected_reasons)


def test_majority_voting_detects_tie_without_clear_direction() -> None:
    result = build_consensus(
        (
            _vote("trend", AIVoteFamily.TREND, VoteDirection.BULLISH, "0.80"),
            _vote("momentum", AIVoteFamily.MOMENTUM, VoteDirection.BEARISH, "0.80"),
            _vote("volatility", AIVoteFamily.VOLATILITY, VoteDirection.NEUTRAL, "0.80"),
        ),
        policy=VotingPolicy(method=VotingMethod.MAJORITY),
        generated_at=NOW,
    )

    assert not result.actionable
    assert "no clear consensus direction" in result.rejected_reasons


def _vote(
    name: str,
    family: AIVoteFamily,
    direction: VoteDirection,
    confidence: str,
    *,
    weight: str = "1",
):
    return deterministic_model_vote(
        model_name=name,
        family=family,
        direction=direction,
        confidence=Decimal(confidence),
        generated_at=NOW,
        inputs_ref="fixture:features",
        rationale=f"{name} fixture vote",
        weight=Decimal(weight),
    )
