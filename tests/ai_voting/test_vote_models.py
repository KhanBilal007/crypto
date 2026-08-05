from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.ai import AIVoteFamily, VoteDirection, deterministic_model_vote

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_optional_low_trust_family_is_degraded_without_deterministic_quality() -> None:
    vote = deterministic_model_vote(
        model_name="sentiment-fixture",
        family=AIVoteFamily.SENTIMENT,
        direction=VoteDirection.BULLISH,
        confidence=Decimal("0.60"),
        generated_at=NOW,
        inputs_ref="fixture:sentiment",
        rationale="sentiment fixture is optional",
        deterministic_source_quality=False,
    )

    assert vote.quality.is_degraded
    assert vote.quality.flags == ("optional_low_trust_model",)
    assert vote.explain()["family"] == "sentiment"


def test_model_vote_rejects_invalid_confidence_and_weight() -> None:
    with pytest.raises(ValueError, match="confidence"):
        deterministic_model_vote(
            model_name="trend",
            family=AIVoteFamily.TREND,
            direction=VoteDirection.BULLISH,
            confidence=Decimal("1.1"),
            generated_at=NOW,
            inputs_ref="fixture",
            rationale="invalid confidence",
        )

    with pytest.raises(ValueError, match="weight"):
        deterministic_model_vote(
            model_name="trend",
            family=AIVoteFamily.TREND,
            direction=VoteDirection.BULLISH,
            confidence=Decimal("0.5"),
            generated_at=NOW,
            inputs_ref="fixture",
            rationale="invalid weight",
            weight=Decimal("0"),
        )
