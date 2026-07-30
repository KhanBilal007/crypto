from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, OrderBookMetrics
from abtp.domain import OrderSide
from abtp.execution import (
    ExecutionOptimizationInput,
    ExecutionTimingAction,
    InstitutionalExecutionPlan,
    InstitutionalExecutionPolicy,
    optimize_institutional_execution,
)

NOW = datetime(2026, 2, 10, tzinfo=UTC)
TEST_POLICY = InstitutionalExecutionPolicy(
    max_slice_count=5,
    max_participation_rate=Decimal("0.20"),
    max_expected_cost_bps=Decimal("90"),
    max_spread_bps=Decimal("40"),
    fee_bps=Decimal("20"),
    base_slice_delay_seconds=30,
)


def test_optimizer_splits_large_order_and_estimates_costs() -> None:
    plan = optimize_institutional_execution(
        _input(quantity=Decimal("30"), ask_depth=Decimal("100")),
        policy=TEST_POLICY,
        generated_at=NOW,
    )

    assert isinstance(plan, InstitutionalExecutionPlan)
    assert plan.advisory_only is True
    assert plan.acceptable_for_execution_review is False
    assert plan.quality.is_degraded
    assert plan.timing_action is ExecutionTimingAction.SPLIT_OVER_TIME
    assert len(plan.slices) == 2
    assert plan.slices[0].quantity == Decimal("15.0000")
    assert plan.slices[1].delay_seconds == 30
    assert plan.spread_bps == Decimal("20.0000")
    assert plan.market_impact_bps == Decimal("45.0000")
    assert plan.slippage_estimate_bps == Decimal("67.5000")
    assert plan.expected_cost_bps == Decimal("87.5000")
    assert plan.audit_payload()["slice_count"] == 2


def test_optimizer_waits_when_spread_is_wide_but_not_rejected() -> None:
    plan = optimize_institutional_execution(
        _input(
            quantity=Decimal("10"),
            best_bid=Decimal("99"),
            best_ask=Decimal("100"),
            ask_depth=Decimal("100"),
            volatility=Decimal("0.10"),
            urgency=Decimal("0.10"),
        ),
        policy=InstitutionalExecutionPolicy(
            max_participation_rate=Decimal("0.20"),
            max_expected_cost_bps=Decimal("95"),
            max_spread_bps=Decimal("60"),
            fee_bps=Decimal("20"),
        ),
        generated_at=NOW,
    )

    assert plan.timing_action is ExecutionTimingAction.WAIT_FOR_SPREAD
    assert plan.quality.is_degraded
    assert "wide_spread_execution_plan" in plan.quality.flags
    assert plan.rejection_reasons == ()


def test_optimizer_blocks_unsafe_cost_or_missing_depth() -> None:
    plan = optimize_institutional_execution(
        _input(quantity=Decimal("100"), ask_depth=Decimal("0")),
        policy=TEST_POLICY,
        generated_at=NOW,
    )

    assert plan.timing_action is ExecutionTimingAction.BLOCKED
    assert plan.quality.is_rejected
    assert not plan.acceptable_for_execution_review
    assert "relevant order-book depth is unavailable" in plan.rejection_reasons
    assert plan.slices[0].rationale == "blocked advisory slice for manual review"


def test_optimizer_rejects_stale_or_rejected_quality() -> None:
    plan = optimize_institutional_execution(
        _input(quality=_rejected_quality(), stale=True),
        policy=TEST_POLICY,
        generated_at=NOW,
    )

    assert plan.quality.is_rejected
    assert "execution optimization input quality is rejected" in plan.rejection_reasons
    assert "execution optimization input is stale" in plan.rejection_reasons
    assert "execution_optimization_rejection" in plan.quality.flags


def test_optimizer_has_no_order_risk_or_submission_authority() -> None:
    plan = optimize_institutional_execution(_input(), policy=TEST_POLICY, generated_at=NOW)

    with pytest.raises(ValueError, match="cannot create order intents"):
        plan.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        plan.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        plan.submit_order()


def test_optimizer_public_imports_and_validation() -> None:
    assert InstitutionalExecutionPlan.__name__ == "InstitutionalExecutionPlan"
    with pytest.raises(ValueError, match="quantity must be positive"):
        _input(quantity=Decimal("0"))


def _input(
    *,
    quantity: Decimal = Decimal("10"),
    best_bid: Decimal = Decimal("99.90"),
    best_ask: Decimal = Decimal("100.10"),
    bid_depth: Decimal = Decimal("100"),
    ask_depth: Decimal = Decimal("100"),
    volatility: Decimal = Decimal("0.50"),
    urgency: Decimal = Decimal("0.50"),
    quality: DataQualityStatus | None = None,
    stale: bool = False,
) -> ExecutionOptimizationInput:
    return ExecutionOptimizationInput(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        quantity=quantity,
        reference_price=Decimal("100"),
        order_book_metrics=OrderBookMetrics(
            best_bid=best_bid,
            best_ask=best_ask,
            spread=best_ask - best_bid,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            imbalance=Decimal("0"),
        ),
        volatility_score=volatility,
        urgency_score=urgency,
        quality=quality or _trusted_quality(),
        observed_at=NOW,
        source_refs={"order_book": "fixture:book"},
        stale=stale,
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:trusted",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_order_book",
                severity=DataTrustLevel.REJECTED,
                reason="fixture rejected order book",
            ),
        ),
        source_ref="fixture:rejected",
        checked_at=NOW,
    )
