from __future__ import annotations

from decimal import Decimal

from abtp.risk import SimulationAssumptions, simulate_capital_paths, summarize_tail_risk


def test_seeded_simulation_is_reproducible() -> None:
    assumptions = _assumptions(seed=17)

    first = simulate_capital_paths(assumptions)
    second = simulate_capital_paths(assumptions)

    assert [path.as_dict() for path in first] == [path.as_dict() for path in second]
    assert len(first) == assumptions.trial_count
    assert all(len(path.steps) == assumptions.horizon_steps for path in first)


def test_different_seed_changes_path_sequence() -> None:
    first = simulate_capital_paths(_assumptions(seed=17))
    second = simulate_capital_paths(_assumptions(seed=18))

    assert [path.as_dict() for path in first] != [path.as_dict() for path in second]


def test_fee_and_slippage_reduce_equity() -> None:
    without_costs = simulate_capital_paths(
        _assumptions(
            seed=1,
            return_samples=(Decimal("0.01"),),
            fee_bps_range=(Decimal("0"), Decimal("0")),
            slippage_bps_range=(Decimal("0"), Decimal("0")),
        )
    )[0]
    with_costs = simulate_capital_paths(
        _assumptions(
            seed=1,
            return_samples=(Decimal("0.01"),),
            fee_bps_range=(Decimal("10"), Decimal("10")),
            slippage_bps_range=(Decimal("20"), Decimal("20")),
        )
    )[0]

    assert with_costs.ending_equity < without_costs.ending_equity
    assert with_costs.steps[0].fee_bps == Decimal("10")
    assert with_costs.steps[0].slippage_bps == Decimal("20")


def test_tail_summary_calculates_survival_and_drawdown() -> None:
    paths = simulate_capital_paths(
        _assumptions(
            seed=7,
            return_samples=(Decimal("-0.20"), Decimal("0.05")),
            position_size_pct=Decimal("1"),
            trial_count=20,
        )
    )

    summary = summarize_tail_risk(paths)

    assert summary.scenario_count == 20
    assert summary.max_drawdown > Decimal("0")
    assert summary.worst_period_loss < Decimal("0")
    assert Decimal("0") <= summary.survival_probability <= Decimal("1")
    assert summary.risk_of_ruin == Decimal("1") - summary.survival_probability


def _assumptions(
    *,
    seed: int,
    return_samples: tuple[Decimal, ...] = (
        Decimal("0.02"),
        Decimal("-0.01"),
        Decimal("0.005"),
    ),
    position_size_pct: Decimal = Decimal("0.5"),
    fee_bps_range: tuple[Decimal, Decimal] = (Decimal("5"), Decimal("5")),
    slippage_bps_range: tuple[Decimal, Decimal] = (Decimal("10"), Decimal("10")),
    trial_count: int = 5,
) -> SimulationAssumptions:
    return SimulationAssumptions(
        starting_equity=Decimal("1000"),
        return_samples=return_samples,
        horizon_steps=4,
        trial_count=trial_count,
        seed=seed,
        position_size_pct=position_size_pct,
        fee_bps_range=fee_bps_range,
        slippage_bps_range=slippage_bps_range,
        source_refs={"returns": "fixture:returns"},
    )
