"""Tail-risk summaries for Monte Carlo scenario paths."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from abtp.risk.simulation import DECIMAL_ONE, DECIMAL_ZERO, ScenarioPath


@dataclass(frozen=True, slots=True)
class TailRiskSummary:
    """Aggregate tail-risk evidence from simulated paths."""

    scenario_count: int
    worst_ending_return: Decimal
    percentile_05_return: Decimal
    expected_shortfall_05: Decimal
    percentile_95_drawdown: Decimal
    max_drawdown: Decimal
    worst_period_loss: Decimal
    survival_probability: Decimal
    risk_of_ruin: Decimal

    def __post_init__(self) -> None:
        if self.scenario_count <= 0:
            raise ValueError("scenario_count must be positive")
        for name, value in (
            ("percentile_95_drawdown", self.percentile_95_drawdown),
            ("max_drawdown", self.max_drawdown),
            ("survival_probability", self.survival_probability),
            ("risk_of_ruin", self.risk_of_ruin),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")

    def as_dict(self) -> dict[str, str | int]:
        return {
            "scenario_count": self.scenario_count,
            "worst_ending_return": str(self.worst_ending_return),
            "percentile_05_return": str(self.percentile_05_return),
            "expected_shortfall_05": str(self.expected_shortfall_05),
            "percentile_95_drawdown": str(self.percentile_95_drawdown),
            "max_drawdown": str(self.max_drawdown),
            "worst_period_loss": str(self.worst_period_loss),
            "survival_probability": str(self.survival_probability),
            "risk_of_ruin": str(self.risk_of_ruin),
        }


def summarize_tail_risk(paths: tuple[ScenarioPath, ...]) -> TailRiskSummary:
    """Summarize deterministic tail-risk metrics from simulated paths."""

    if not paths:
        raise ValueError("scenario paths are required")
    ending_returns = tuple(sorted(path.net_return for path in paths))
    drawdowns = tuple(sorted(path.max_drawdown for path in paths))
    period_losses = tuple(step.net_return for path in paths for step in path.steps)
    percentile_05 = _percentile_nearest_rank(ending_returns, Decimal("0.05"))
    tail_returns = tuple(value for value in ending_returns if value <= percentile_05)
    survival_count = sum(1 for path in paths if path.survived)
    survival_probability = Decimal(survival_count) / Decimal(len(paths))
    return TailRiskSummary(
        scenario_count=len(paths),
        worst_ending_return=ending_returns[0],
        percentile_05_return=percentile_05,
        expected_shortfall_05=_mean(tail_returns),
        percentile_95_drawdown=_percentile_nearest_rank(drawdowns, Decimal("0.95")),
        max_drawdown=drawdowns[-1],
        worst_period_loss=min(period_losses, default=DECIMAL_ZERO),
        survival_probability=survival_probability,
        risk_of_ruin=DECIMAL_ONE - survival_probability,
    )


def _percentile_nearest_rank(values: tuple[Decimal, ...], percentile: Decimal) -> Decimal:
    if not values:
        return DECIMAL_ZERO
    rank = int((Decimal(len(values)) * percentile).to_integral_value(rounding=ROUND_CEILING))
    index = min(max(rank - 1, 0), len(values) - 1)
    return values[index]


def _mean(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        return DECIMAL_ZERO
    return sum(values, DECIMAL_ZERO) / Decimal(len(values))
