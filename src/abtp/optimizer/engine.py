"""AI Strategy Optimiser orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from abtp.config import TradingMode
from abtp.domain.models import JsonValue
from abtp.optimizer.scorer import (
    StrategyMetricSnapshot,
    StrategyScore,
    StrategyScoringPolicy,
    score_strategies,
)
from abtp.optimizer.selector import (
    StrategyRecommendation,
    StrategySelectionPolicy,
    select_strategy,
)


@dataclass(frozen=True, slots=True)
class StrategyOptimisationRequest:
    """Input request for one strategy optimisation review."""

    candidates: tuple[StrategyMetricSnapshot, ...]
    regime_label: str
    mode: TradingMode = TradingMode.PAPER
    generated_at: datetime | None = None
    manual_approval_for_live_change: bool = False
    risk_limits_ref: str = "config:risk_limits"
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.regime_label.strip():
            raise ValueError("regime_label is required")
        if not self.risk_limits_ref.strip():
            raise ValueError("risk_limits_ref is required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class OptimisationReport:
    """Auditable optimiser report."""

    generated_at: datetime
    regime_label: str
    scores: tuple[StrategyScore, ...]
    recommendation: StrategyRecommendation
    risk_limits_ref: str
    source_refs: Mapping[str, str]
    limitations: tuple[str, ...] = (
        "Optimiser recommendations are advisory and cannot create orders.",
        "All future signals must pass the Strategy Engine and Risk Management Engine.",
        "Live strategy changes require manual approval.",
        "No profit is guaranteed by optimiser rankings.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "regime_label": self.regime_label,
            "scores": [score.as_dict() for score in self.scores],
            "recommendation": self.recommendation.as_dict(),
            "risk_limits_ref": self.risk_limits_ref,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "regime_label": self.regime_label,
            "selected_strategy": self.recommendation.selected_strategy or "none",
            "confidence_score": str(self.recommendation.confidence_score),
            "rejected_reasons": "|".join(self.recommendation.rejected_reasons),
            "ranked_strategies": "|".join(score.strategy_name for score in self.scores),
            "risk_limits_ref": self.risk_limits_ref,
        }


class StrategyOptimiserEngine:
    """Score and select strategies without signal, risk, or execution authority."""

    def __init__(
        self,
        *,
        scoring_policy: StrategyScoringPolicy | None = None,
        selection_policy: StrategySelectionPolicy | None = None,
    ) -> None:
        self._scoring_policy = scoring_policy or StrategyScoringPolicy()
        self._selection_policy = selection_policy or StrategySelectionPolicy()

    @property
    def scoring_policy(self) -> StrategyScoringPolicy:
        return self._scoring_policy

    @property
    def selection_policy(self) -> StrategySelectionPolicy:
        return self._selection_policy

    def optimise(self, request: StrategyOptimisationRequest) -> OptimisationReport:
        """Return an advisory optimisation report."""

        generated_at = request.generated_at or datetime.now(UTC)
        scores = score_strategies(
            request.candidates,
            regime_label=request.regime_label,
            policy=self._scoring_policy,
        )
        recommendation = select_strategy(
            scores,
            mode=request.mode,
            generated_at=generated_at,
            policy=self._selection_policy,
            manual_approval_for_live_change=request.manual_approval_for_live_change,
            source_refs=request.source_refs,
        )
        return OptimisationReport(
            generated_at=generated_at,
            regime_label=request.regime_label,
            scores=scores,
            recommendation=recommendation,
            risk_limits_ref=request.risk_limits_ref,
            source_refs=request.source_refs,
        )

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject direct order submission; optimiser has no execution authority."""

        raise ValueError("strategy optimiser cannot submit orders")

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        """Reject direct signal creation; strategy plugins own signal generation."""

        raise ValueError("strategy optimiser cannot create strategy signals")


def optimiser_confidence_adjustment(report: OptimisationReport) -> Decimal:
    """Return a small advisory confidence context value for future consumers."""

    if not report.recommendation.recommended:
        return Decimal("0")
    return min(Decimal("0.10"), report.recommendation.confidence_score / Decimal("10"))
