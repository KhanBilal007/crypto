from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.ai import (
    AIVoteFamily,
    MultiAIVotingEngine,
    VoteDirection,
    VotingRequest,
    consensus_score_to_confidence_adjustment,
    deterministic_model_vote,
)
from abtp.data import DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, AssetPair
from abtp.features import FEATURE_SCHEMA_VERSION, FeatureSnapshot

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PAIR = AssetPair(Asset("BTC"), Asset("USDT"))


@dataclass(frozen=True, slots=True)
class StubVoteModel:
    model_name: str
    family: AIVoteFamily
    direction: VoteDirection
    confidence: Decimal

    def vote(self, snapshot: FeatureSnapshot):
        return deterministic_model_vote(
            model_name=self.model_name,
            family=self.family,
            direction=self.direction,
            confidence=self.confidence,
            generated_at=snapshot.generated_at,
            inputs_ref=snapshot.inputs_ref,
            rationale=f"{self.model_name} stub vote",
        )


def test_voting_engine_combines_supplied_and_model_votes() -> None:
    engine = MultiAIVotingEngine(
        (
            StubVoteModel("trend", AIVoteFamily.TREND, VoteDirection.BULLISH, Decimal("0.80")),
            StubVoteModel(
                "momentum",
                AIVoteFamily.MOMENTUM,
                VoteDirection.BULLISH,
                Decimal("0.70"),
            ),
        )
    )
    supplied = deterministic_model_vote(
        model_name="orderbook",
        family=AIVoteFamily.ORDER_BOOK,
        direction=VoteDirection.BULLISH,
        confidence=Decimal("0.65"),
        generated_at=NOW,
        inputs_ref="fixture:orderbook",
        rationale="supplied order-book vote",
    )

    result = engine.evaluate(VotingRequest(snapshot=_snapshot(), votes=(supplied,)))

    assert result.actionable
    assert result.direction is VoteDirection.BULLISH
    assert result.source_refs["features"].startswith("features:stage-015.v1")
    assert consensus_score_to_confidence_adjustment(result) == Decimal("0.10")


def test_voting_engine_has_no_order_authority() -> None:
    engine = MultiAIVotingEngine()

    with pytest.raises(ValueError, match="cannot submit orders"):
        engine.submit_order(object())


def test_public_imports_are_available() -> None:
    import abtp.ai as ai

    assert ai.MultiAIVotingEngine is MultiAIVotingEngine
    assert ai.VoteDirection.BULLISH.value == "bullish"


def _snapshot() -> FeatureSnapshot:
    return FeatureSnapshot(
        pair=PAIR,
        generated_at=NOW,
        schema_version=FEATURE_SCHEMA_VERSION,
        values={
            "market.close": Decimal("100"),
            "market.return_1": Decimal("0.01"),
        },
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref="fixture:features",
            checked_at=NOW,
        ),
        lookback_start=NOW - timedelta(hours=3),
        lookback_end=NOW,
        source_refs={"fixture": "features"},
    )
