from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.risk import (
    MonteCarloRiskLimits,
    MonteCarloRiskReport,
    SimulationAssumptions,
    run_monte_carlo_risk_simulation,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_safe_simulation_report_is_trusted_and_auditable() -> None:
    report = run_monte_carlo_risk_simulation(
        _assumptions(return_samples=(Decimal("0.01"), Decimal("0.02"), Decimal("-0.002"))),
        generated_at=NOW,
        source_refs={"backtest": "fixture:run:1"},
    )

    assert isinstance(report, MonteCarloRiskReport)
    assert report.acceptable_for_risk_review
    assert report.allocation_multiplier == Decimal("1")
    assert report.rejection_reasons == ()
    assert report.audit_payload()["seed"] == "11"
    assert report.as_dict()["source_refs"]["backtest"] == "fixture:run:1"  # type: ignore[index]


def test_unsafe_survival_and_drawdown_fail_closed() -> None:
    report = run_monte_carlo_risk_simulation(
        _assumptions(
            return_samples=(Decimal("-0.25"), Decimal("-0.20"), Decimal("0.03")),
            position_size_pct=Decimal("1"),
            trial_count=50,
        ),
        limits=MonteCarloRiskLimits(
            max_drawdown=Decimal("0.10"),
            max_tail_loss=Decimal("0.08"),
            min_survival_probability=Decimal("0.95"),
            max_risk_of_ruin=Decimal("0.05"),
        ),
        generated_at=NOW,
    )

    assert not report.acceptable_for_risk_review
    assert report.allocation_multiplier == Decimal("0")
    assert report.quality.is_rejected
    assert any("drawdown" in reason for reason in report.rejection_reasons)
    assert any("survival probability" in reason for reason in report.rejection_reasons)


def test_marginal_survival_reduces_allocation_without_rejection() -> None:
    report = run_monte_carlo_risk_simulation(
        _assumptions(
            return_samples=(Decimal("-0.12"), Decimal("0.02"), Decimal("0.03")),
            position_size_pct=Decimal("1"),
            ruin_equity_pct=Decimal("0.90"),
            trial_count=30,
        ),
        limits=MonteCarloRiskLimits(
            max_drawdown=Decimal("0.60"),
            max_tail_loss=Decimal("0.35"),
            min_survival_probability=Decimal("0.30"),
            max_risk_of_ruin=Decimal("0.70"),
            reduce_allocation_below_survival_probability=Decimal("1"),
        ),
        generated_at=NOW,
    )

    assert report.rejection_reasons == ()
    assert report.allocation_multiplier == Decimal("0.50")
    assert report.quality.is_degraded
    assert not report.acceptable_for_risk_review


def test_report_has_no_trading_or_risk_approval_authority() -> None:
    report = run_monte_carlo_risk_simulation(_assumptions(), generated_at=NOW)

    with pytest.raises(ValueError, match="cannot create strategy signals"):
        report.create_signal()
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()


def test_invalid_assumptions_fail_fast() -> None:
    with pytest.raises(ValueError, match="return_samples are required"):
        SimulationAssumptions(
            starting_equity=Decimal("1000"),
            return_samples=(),
            horizon_steps=3,
            trial_count=10,
            seed=1,
        )


def _assumptions(
    *,
    return_samples: tuple[Decimal, ...] = (
        Decimal("0.01"),
        Decimal("-0.005"),
        Decimal("0.02"),
    ),
    position_size_pct: Decimal = Decimal("0.50"),
    trial_count: int = 20,
    ruin_equity_pct: Decimal = Decimal("0.70"),
) -> SimulationAssumptions:
    return SimulationAssumptions(
        starting_equity=Decimal("1000"),
        return_samples=return_samples,
        horizon_steps=5,
        trial_count=trial_count,
        seed=11,
        position_size_pct=position_size_pct,
        fee_bps_range=(Decimal("5"), Decimal("5")),
        slippage_bps_range=(Decimal("10"), Decimal("10")),
        ruin_equity_pct=ruin_equity_pct,
        volatility_regime="fixture",
        source_refs={"returns": "fixture:returns"},
    )
