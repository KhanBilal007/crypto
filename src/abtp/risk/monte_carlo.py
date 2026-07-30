"""Advisory Monte Carlo risk simulator."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.risk.simulation import (
    DECIMAL_ONE,
    DECIMAL_ZERO,
    ScenarioPath,
    SimulationAssumptions,
    simulate_capital_paths,
)
from abtp.risk.tail_risk import TailRiskSummary, summarize_tail_risk


@dataclass(frozen=True, slots=True)
class MonteCarloRiskLimits:
    """Conservative rejection thresholds for simulation outputs."""

    max_drawdown: Decimal = Decimal("0.20")
    max_tail_loss: Decimal = Decimal("0.10")
    min_survival_probability: Decimal = Decimal("0.95")
    max_risk_of_ruin: Decimal = Decimal("0.05")
    reduce_allocation_below_survival_probability: Decimal = Decimal("0.98")
    policy_version: str = "stage-044.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("max_drawdown", self.max_drawdown),
            ("max_tail_loss", self.max_tail_loss),
            ("min_survival_probability", self.min_survival_probability),
            ("max_risk_of_ruin", self.max_risk_of_ruin),
            (
                "reduce_allocation_below_survival_probability",
                self.reduce_allocation_below_survival_probability,
            ),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")

    def as_dict(self) -> dict[str, str]:
        return {
            "max_drawdown": str(self.max_drawdown),
            "max_tail_loss": str(self.max_tail_loss),
            "min_survival_probability": str(self.min_survival_probability),
            "max_risk_of_ruin": str(self.max_risk_of_ruin),
            "reduce_allocation_below_survival_probability": str(
                self.reduce_allocation_below_survival_probability
            ),
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True, slots=True)
class MonteCarloRiskReport:
    """Explainable Monte Carlo risk evidence."""

    generated_at: datetime
    assumptions: SimulationAssumptions
    limits: MonteCarloRiskLimits
    paths: tuple[ScenarioPath, ...]
    tail_summary: TailRiskSummary
    rejection_reasons: tuple[str, ...]
    allocation_multiplier: Decimal
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Monte Carlo output is advisory risk evidence only.",
        "The simulator does not create signals, risk approvals, order intents, or execution.",
        "Results depend on supplied return samples, costs, slippage, seed, and limits.",
        "No profit is guaranteed by simulation output.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if not self.paths:
            raise ValueError("Monte Carlo report requires scenario paths")
        if not DECIMAL_ZERO <= self.allocation_multiplier <= DECIMAL_ONE:
            raise ValueError("allocation_multiplier must be between 0 and 1")
        if not self.limitations:
            raise ValueError("Monte Carlo report limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def acceptable_for_risk_review(self) -> bool:
        return not self.rejection_reasons and self.quality.is_trusted

    def as_dict(self, *, include_paths: bool = False) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "assumptions": self.assumptions.as_dict(),
            "limits": self.limits.as_dict(),
            "tail_summary": self.tail_summary.as_dict(),
            "scenario_count": len(self.paths),
            "rejection_reasons": list(self.rejection_reasons),
            "allocation_multiplier": str(self.allocation_multiplier),
            "acceptable_for_risk_review": self.acceptable_for_risk_review,
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
            "paths": [path.as_dict() for path in self.paths] if include_paths else [],
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "seed": str(self.assumptions.seed),
            "trial_count": str(self.assumptions.trial_count),
            "horizon_steps": str(self.assumptions.horizon_steps),
            "survival_probability": str(self.tail_summary.survival_probability),
            "risk_of_ruin": str(self.tail_summary.risk_of_ruin),
            "max_drawdown": str(self.tail_summary.max_drawdown),
            "percentile_05_return": str(self.tail_summary.percentile_05_return),
            "allocation_multiplier": str(self.allocation_multiplier),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "policy_version": self.limits.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        """Reject strategy authority."""

        raise ValueError("Monte Carlo risk report cannot create strategy signals")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        """Reject risk-approval authority."""

        raise ValueError("Monte Carlo risk report cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject execution authority."""

        raise ValueError("Monte Carlo risk report cannot submit orders")


def run_monte_carlo_risk_simulation(
    assumptions: SimulationAssumptions,
    *,
    limits: MonteCarloRiskLimits | None = None,
    generated_at: datetime | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> MonteCarloRiskReport:
    """Run seeded simulations and return advisory risk evidence."""

    active_limits = limits or MonteCarloRiskLimits()
    checked_at = normalize_timestamp(generated_at or datetime.now(UTC))
    paths = simulate_capital_paths(assumptions)
    tail_summary = summarize_tail_risk(paths)
    rejection_reasons = _rejection_reasons(tail_summary, active_limits)
    allocation_multiplier = _allocation_multiplier(tail_summary, active_limits, rejection_reasons)
    refs = dict(assumptions.source_refs)
    refs.update(source_refs or {})
    quality = _quality_status(
        tail_summary,
        active_limits,
        rejection_reasons=rejection_reasons,
        checked_at=checked_at,
    )
    return MonteCarloRiskReport(
        generated_at=checked_at,
        assumptions=assumptions,
        limits=active_limits,
        paths=paths,
        tail_summary=tail_summary,
        rejection_reasons=rejection_reasons,
        allocation_multiplier=allocation_multiplier,
        quality=quality,
        source_refs=refs,
    )


def _rejection_reasons(summary: TailRiskSummary, limits: MonteCarloRiskLimits) -> tuple[str, ...]:
    reasons: list[str] = []
    if summary.max_drawdown > limits.max_drawdown:
        reasons.append(f"max drawdown {summary.max_drawdown} exceeds limit {limits.max_drawdown}")
    if summary.percentile_05_return < -limits.max_tail_loss:
        reasons.append(
            f"5th percentile return {summary.percentile_05_return} breaches tail-loss limit "
            f"-{limits.max_tail_loss}"
        )
    if summary.survival_probability < limits.min_survival_probability:
        reasons.append(
            f"survival probability {summary.survival_probability} is below minimum "
            f"{limits.min_survival_probability}"
        )
    if summary.risk_of_ruin > limits.max_risk_of_ruin:
        reasons.append(
            f"risk of ruin {summary.risk_of_ruin} exceeds limit {limits.max_risk_of_ruin}"
        )
    return tuple(dict.fromkeys(reasons))


def _allocation_multiplier(
    summary: TailRiskSummary,
    limits: MonteCarloRiskLimits,
    rejection_reasons: tuple[str, ...],
) -> Decimal:
    if rejection_reasons:
        return DECIMAL_ZERO
    if summary.survival_probability < limits.reduce_allocation_below_survival_probability:
        return Decimal("0.50")
    if summary.percentile_95_drawdown > limits.max_drawdown * Decimal("0.75"):
        return Decimal("0.75")
    return DECIMAL_ONE


def _quality_status(
    summary: TailRiskSummary,
    limits: MonteCarloRiskLimits,
    *,
    rejection_reasons: tuple[str, ...],
    checked_at: datetime,
) -> DataQualityStatus:
    issues: list[DataQualityIssue] = []
    for reason in rejection_reasons:
        issues.append(
            DataQualityIssue(
                flag="monte_carlo_rejection",
                severity=DataTrustLevel.REJECTED,
                reason=reason,
            )
        )
    if (
        not rejection_reasons
        and summary.survival_probability < limits.reduce_allocation_below_survival_probability
    ):
        issues.append(
            DataQualityIssue(
                flag="monte_carlo_reduce_allocation",
                severity=DataTrustLevel.DEGRADED,
                reason="survival probability is below allocation-comfort threshold",
            )
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
        source_ref="risk:monte_carlo",
        checked_at=checked_at,
    )
