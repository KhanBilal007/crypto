from __future__ import annotations

from decimal import Decimal

from abtp.lab import (
    ParameterCandidate,
    ParameterSearchSpace,
    ParameterSpec,
    generate_parameter_candidates,
    merge_candidate_overrides,
    rank_candidate_results,
)


def test_parameter_search_generates_bounded_deterministic_candidates() -> None:
    space = ParameterSearchSpace(
        strategy_key="trend-v1",
        parameters=(
            ParameterSpec(
                name="lookback",
                minimum=Decimal("10"),
                maximum=Decimal("12"),
                step=Decimal("1"),
                default=Decimal("11"),
            ),
            ParameterSpec(
                name="risk_multiplier",
                minimum=Decimal("0.5"),
                maximum=Decimal("1.0"),
                step=Decimal("0.5"),
                default=Decimal("0.5"),
            ),
        ),
        max_candidates=4,
    )

    candidates = generate_parameter_candidates(space)

    assert len(candidates) == 4
    assert candidates[0].strategy_key == "trend-v1"
    assert candidates[0].values == {"lookback": Decimal("10"), "risk_multiplier": Decimal("0.5")}
    assert all(
        candidate.candidate_ref.startswith("trend-v1:candidate:") for candidate in candidates
    )


def test_default_candidate_is_preserved_when_search_space_is_truncated() -> None:
    space = ParameterSearchSpace(
        strategy_key="trend-v1",
        parameters=(
            ParameterSpec(
                name="lookback",
                minimum=Decimal("10"),
                maximum=Decimal("20"),
                step=Decimal("1"),
                default=Decimal("20"),
            ),
        ),
        max_candidates=2,
    )

    candidates = generate_parameter_candidates(space)

    assert candidates[0].values == {"lookback": Decimal("20")}
    assert candidates[0].candidate_ref == "trend-v1:candidate:default"


def test_candidate_overrides_and_ranking_do_not_mutate_source() -> None:
    candidate = ParameterCandidate(
        strategy_key="trend-v1",
        values={"lookback": Decimal("12")},
        candidate_ref="trend-v1:candidate:000",
        source_ref="fixture:space",
    )

    overridden = merge_candidate_overrides(candidate, {"lookback": Decimal("14")})
    ranked = rank_candidate_results(
        (candidate, overridden),
        {
            candidate.candidate_ref: Decimal("0.4"),
            overridden.candidate_ref: Decimal("0.8"),
        },
    )

    assert candidate.values["lookback"] == Decimal("12")
    assert overridden.values["lookback"] == Decimal("14")
    assert ranked[0] == overridden
