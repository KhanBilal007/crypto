"""Multi-AI voting orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from abtp.ai.consensus import ConsensusResult, VotingPolicy, build_consensus
from abtp.ai.vote_models import ModelVote
from abtp.features import FeatureSnapshot


class VoteModel(Protocol):
    """Provider-neutral deterministic model-vote interface."""

    def vote(self, snapshot: FeatureSnapshot) -> ModelVote:
        """Return a model vote without signal, risk, or order authority."""


@dataclass(frozen=True, slots=True)
class VotingRequest:
    """Input to the Multi-AI voting engine."""

    snapshot: FeatureSnapshot
    votes: tuple[ModelVote, ...] = ()
    generated_at: datetime | None = None
    source_ref: str = "ai_voting:request"

    def __post_init__(self) -> None:
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")


class MultiAIVotingEngine:
    """Combine independent model votes into advisory consensus context."""

    def __init__(
        self,
        models: Sequence[VoteModel] = (),
        *,
        policy: VotingPolicy | None = None,
    ) -> None:
        self._models = tuple(models)
        self._policy = policy or VotingPolicy()

    @property
    def policy(self) -> VotingPolicy:
        return self._policy

    def evaluate(self, request: VotingRequest) -> ConsensusResult:
        """Evaluate supplied and configured model votes."""

        model_votes = tuple(model.vote(request.snapshot) for model in self._models)
        votes = (*request.votes, *model_votes)
        return build_consensus(
            votes,
            policy=self._policy,
            generated_at=request.generated_at or request.snapshot.generated_at,
            source_refs={
                "features": request.snapshot.inputs_ref,
                "request": request.source_ref,
            },
        )

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject direct order submission; voting has no execution authority."""

        raise ValueError("multi-AI voting cannot submit orders")


def consensus_score_to_confidence_adjustment(
    result: ConsensusResult,
    *,
    max_adjustment: Decimal = Decimal("0.10"),
) -> Decimal:
    """Map consensus strength to a small advisory confidence adjustment."""

    if max_adjustment < Decimal("0"):
        raise ValueError("max_adjustment cannot be negative")
    if not result.actionable:
        return Decimal("0")
    return max(-max_adjustment, min(max_adjustment, result.consensus_score * max_adjustment))
