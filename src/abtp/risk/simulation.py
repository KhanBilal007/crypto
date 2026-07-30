"""Seeded Monte Carlo capital-path simulation contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from random import Random

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
BPS = Decimal("10000")


@dataclass(frozen=True, slots=True)
class SimulationAssumptions:
    """Inputs for deterministic Monte Carlo risk simulation."""

    starting_equity: Decimal
    return_samples: tuple[Decimal, ...]
    horizon_steps: int
    trial_count: int
    seed: int
    position_size_pct: Decimal = Decimal("0.10")
    fee_bps_range: tuple[Decimal, Decimal] = (Decimal("5"), Decimal("15"))
    slippage_bps_range: tuple[Decimal, Decimal] = (Decimal("0"), Decimal("25"))
    ruin_equity_pct: Decimal = Decimal("0.70")
    volatility_regime: str = "unknown"
    source_refs: Mapping[str, str] = field(default_factory=dict)
    policy_version: str = "stage-044.v1"

    def __post_init__(self) -> None:
        if self.starting_equity <= DECIMAL_ZERO:
            raise ValueError("starting_equity must be positive")
        if not self.return_samples:
            raise ValueError("return_samples are required")
        if any(not sample.is_finite() for sample in self.return_samples):
            raise ValueError("return_samples must be finite")
        if self.horizon_steps <= 0:
            raise ValueError("horizon_steps must be positive")
        if self.trial_count <= 0:
            raise ValueError("trial_count must be positive")
        if not DECIMAL_ZERO <= self.position_size_pct <= DECIMAL_ONE:
            raise ValueError("position_size_pct must be between 0 and 1")
        _validate_bps_range(self.fee_bps_range, "fee_bps_range")
        _validate_bps_range(self.slippage_bps_range, "slippage_bps_range")
        if not DECIMAL_ZERO <= self.ruin_equity_pct <= DECIMAL_ONE:
            raise ValueError("ruin_equity_pct must be between 0 and 1")
        if not self.volatility_regime.strip():
            raise ValueError("volatility_regime is required")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def ruin_equity(self) -> Decimal:
        return self.starting_equity * self.ruin_equity_pct

    def as_dict(self) -> dict[str, object]:
        return {
            "starting_equity": str(self.starting_equity),
            "return_samples": [str(sample) for sample in self.return_samples],
            "horizon_steps": self.horizon_steps,
            "trial_count": self.trial_count,
            "seed": self.seed,
            "position_size_pct": str(self.position_size_pct),
            "fee_bps_range": [str(value) for value in self.fee_bps_range],
            "slippage_bps_range": [str(value) for value in self.slippage_bps_range],
            "ruin_equity_pct": str(self.ruin_equity_pct),
            "ruin_equity": str(self.ruin_equity),
            "volatility_regime": self.volatility_regime,
            "source_refs": dict(self.source_refs),
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True, slots=True)
class ScenarioStep:
    """One simulated capital-path step."""

    step_index: int
    sampled_return: Decimal
    fee_bps: Decimal
    slippage_bps: Decimal
    net_return: Decimal
    equity: Decimal

    def __post_init__(self) -> None:
        if self.step_index < 0:
            raise ValueError("step_index cannot be negative")
        if self.fee_bps < DECIMAL_ZERO or self.slippage_bps < DECIMAL_ZERO:
            raise ValueError("fee_bps and slippage_bps cannot be negative")
        if self.equity < DECIMAL_ZERO:
            raise ValueError("equity cannot be negative")

    def as_dict(self) -> dict[str, str | int]:
        return {
            "step_index": self.step_index,
            "sampled_return": str(self.sampled_return),
            "fee_bps": str(self.fee_bps),
            "slippage_bps": str(self.slippage_bps),
            "net_return": str(self.net_return),
            "equity": str(self.equity),
        }


@dataclass(frozen=True, slots=True)
class ScenarioPath:
    """One simulated capital path with drawdown and survival evidence."""

    trial_index: int
    seed: int
    starting_equity: Decimal
    steps: tuple[ScenarioStep, ...]
    ruin_equity: Decimal

    def __post_init__(self) -> None:
        if self.trial_index < 0:
            raise ValueError("trial_index cannot be negative")
        if self.starting_equity <= DECIMAL_ZERO:
            raise ValueError("starting_equity must be positive")
        if not self.steps:
            raise ValueError("scenario path requires steps")
        if self.ruin_equity < DECIMAL_ZERO:
            raise ValueError("ruin_equity cannot be negative")

    @property
    def ending_equity(self) -> Decimal:
        return self.steps[-1].equity

    @property
    def equity_curve(self) -> tuple[Decimal, ...]:
        return (self.starting_equity, *(step.equity for step in self.steps))

    @property
    def net_return(self) -> Decimal:
        return self.ending_equity / self.starting_equity - DECIMAL_ONE

    @property
    def max_drawdown(self) -> Decimal:
        return _calculate_max_drawdown(self.equity_curve)

    @property
    def tail_loss(self) -> Decimal:
        return min((step.net_return for step in self.steps), default=DECIMAL_ZERO)

    @property
    def survived(self) -> bool:
        return all(equity >= self.ruin_equity for equity in self.equity_curve)

    def as_dict(self) -> dict[str, object]:
        return {
            "trial_index": self.trial_index,
            "seed": self.seed,
            "starting_equity": str(self.starting_equity),
            "ending_equity": str(self.ending_equity),
            "net_return": str(self.net_return),
            "max_drawdown": str(self.max_drawdown),
            "tail_loss": str(self.tail_loss),
            "survived": self.survived,
            "ruin_equity": str(self.ruin_equity),
            "steps": [step.as_dict() for step in self.steps],
        }


def simulate_capital_paths(assumptions: SimulationAssumptions) -> tuple[ScenarioPath, ...]:
    """Run deterministic-seeded Monte Carlo capital paths."""

    rng = Random(assumptions.seed)
    return tuple(
        _simulate_path(assumptions, trial_index=trial_index, rng=rng)
        for trial_index in range(assumptions.trial_count)
    )


def _simulate_path(
    assumptions: SimulationAssumptions, *, trial_index: int, rng: Random
) -> ScenarioPath:
    equity = assumptions.starting_equity
    steps: list[ScenarioStep] = []
    for step_index in range(assumptions.horizon_steps):
        sampled_return = assumptions.return_samples[rng.randrange(len(assumptions.return_samples))]
        fee_bps = _sample_bps(assumptions.fee_bps_range, rng)
        slippage_bps = _sample_bps(assumptions.slippage_bps_range, rng)
        cost_return = (fee_bps + slippage_bps) / BPS * assumptions.position_size_pct
        net_return = sampled_return * assumptions.position_size_pct - cost_return
        equity = max(DECIMAL_ZERO, equity * (DECIMAL_ONE + net_return))
        steps.append(
            ScenarioStep(
                step_index=step_index,
                sampled_return=sampled_return,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                net_return=net_return,
                equity=equity,
            )
        )
    return ScenarioPath(
        trial_index=trial_index,
        seed=assumptions.seed,
        starting_equity=assumptions.starting_equity,
        steps=tuple(steps),
        ruin_equity=assumptions.ruin_equity,
    )


def _sample_bps(value_range: tuple[Decimal, Decimal], rng: Random) -> Decimal:
    low, high = value_range
    ratio = Decimal(rng.randrange(0, 10001)) / Decimal("10000")
    return low + (high - low) * ratio


def _validate_bps_range(value_range: tuple[Decimal, Decimal], name: str) -> None:
    low, high = value_range
    if low < DECIMAL_ZERO or high < DECIMAL_ZERO:
        raise ValueError(f"{name} cannot contain negative values")
    if high < low:
        raise ValueError(f"{name} high value cannot be below low value")


def _calculate_max_drawdown(equity_curve: tuple[Decimal, ...]) -> Decimal:
    peak = equity_curve[0]
    max_drawdown = DECIMAL_ZERO
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > DECIMAL_ZERO:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return max_drawdown
