from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from abtp.data import OrderBookMetrics
from abtp.domain import (
    Asset,
    AssetPair,
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskCheck,
    RiskDecision,
    RiskDecisionStatus,
    Signal,
    SignalDirection,
)
from abtp.execution import (
    ExecutionLatencyRecord,
    ExecutionObservation,
    ExecutionResult,
    OrderRouterConfig,
    PaperOrderRouter,
    PaperSafeExecutionEngine,
    analyze_execution_quality,
    build_execution_quality_report,
    calculate_slippage_bps,
    estimate_market_impact_bps,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_slippage_bps_handles_buy_and_sell_adverse_direction() -> None:
    assert calculate_slippage_bps(
        expected_price=Decimal("100"),
        fill_price=Decimal("101"),
        side=OrderSide.BUY,
    ) == Decimal("100.00")
    assert calculate_slippage_bps(
        expected_price=Decimal("100"),
        fill_price=Decimal("99"),
        side=OrderSide.SELL,
    ) == Decimal("100.00")
    assert calculate_slippage_bps(
        expected_price=Decimal("100"),
        fill_price=Decimal("99"),
        side=OrderSide.BUY,
    ) == Decimal("-100.00")


def test_quality_score_warns_on_partial_fill_and_fee_impact() -> None:
    result = _execution_result(
        quantity=Decimal("0.02"),
        execution_price=Decimal("100"),
        fill_ratio=Decimal("0.5"),
        fee_bps=Decimal("40"),
    )
    observation = _observation(result, expected_price=Decimal("100"))

    score = analyze_execution_quality(observation)

    assert score.fill_ratio == Decimal("0.5")
    assert score.fee_bps == Decimal("40.0")
    assert "partial fill ratio is below threshold" in score.warning_reasons
    assert "fee impact exceeds threshold" in score.warning_reasons
    assert score.acceptable


def test_latency_thresholds_emit_explainable_warnings() -> None:
    result = _execution_result(execution_price=Decimal("100"))
    observation = _observation(
        result,
        expected_price=Decimal("100"),
        latency=ExecutionLatencyRecord(
            submitted_at=NOW,
            acknowledged_at=NOW + timedelta(seconds=2),
            completed_at=NOW + timedelta(seconds=8),
        ),
    )

    score = analyze_execution_quality(observation)

    assert score.acknowledgement_latency_ms == 2000
    assert score.fill_latency_ms == 8000
    assert "acknowledgement latency exceeds threshold" in score.warning_reasons
    assert "fill latency exceeds threshold" in score.warning_reasons


def test_market_impact_uses_order_book_depth_and_spread() -> None:
    result = _execution_result(quantity=Decimal("1"), execution_price=Decimal("100"))
    metrics = OrderBookMetrics(
        best_bid=Decimal("99"),
        best_ask=Decimal("101"),
        spread=Decimal("2"),
        bid_depth=Decimal("5"),
        ask_depth=Decimal("2"),
        imbalance=Decimal("0"),
    )

    impact = estimate_market_impact_bps(
        result.intent,
        fill_summary=result.fill_summary,
        order_book_metrics=metrics,
    )

    assert impact == Decimal("250.0")


def test_execution_quality_report_is_auditable_and_read_only() -> None:
    good_result = _execution_result(execution_price=Decimal("100"))
    poor_result = _execution_result(
        quantity=Decimal("0.02"),
        execution_price=Decimal("101"),
        fill_ratio=Decimal("0.5"),
        fee_bps=Decimal("40"),
    )
    report = build_execution_quality_report(
        (
            _observation(good_result, expected_price=Decimal("100")),
            _observation(poor_result, expected_price=Decimal("100")),
        ),
        generated_at=NOW,
        source_refs={"orders": "fixture:execution_quality"},
    )

    assert len(report.scores) == 2
    assert not report.acceptable
    assert report.quality.is_rejected
    assert report.audit_payload()["order_count"] == "2"
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order(object())
    with pytest.raises(ValueError, match="cannot cancel orders"):
        report.cancel_order(object())


def test_failed_execution_result_rejects_quality() -> None:
    result = _execution_result(execution_price=Decimal("100"))
    failed = result.__class__(
        intent=result.intent,
        idempotency_key=result.idempotency_key,
        accepted=False,
        status=OrderStatus.FAILED,
        route_result=result.route_result,
        fill_summary=result.fill_summary,
        lifecycle_event_ids=result.lifecycle_event_ids,
        audit_event_id=result.audit_event_id,
        reason="fixture failed",
    )

    score = analyze_execution_quality(_observation(failed, expected_price=Decimal("100")))

    assert "order status is failed" in score.rejection_reasons


def test_public_imports_are_available() -> None:
    import abtp.execution as execution

    assert execution.analyze_execution_quality is analyze_execution_quality


def _execution_result(
    *,
    quantity: Decimal = Decimal("0.01"),
    execution_price: Decimal,
    fill_ratio: Decimal = Decimal("1"),
    fee_bps: Decimal = Decimal("20"),
) -> ExecutionResult:
    engine = PaperSafeExecutionEngine(
        router=PaperOrderRouter(config=OrderRouterConfig(fill_ratio=fill_ratio, fee_bps=fee_bps))
    )
    return engine.submit(
        _approved_intent(quantity=quantity),
        idempotency_key=f"fixture-{quantity}-{execution_price}-{fill_ratio}-{fee_bps}",
        submitted_at=NOW,
        execution_price=execution_price,
    )


def _observation(
    result: ExecutionResult,
    *,
    expected_price: Decimal,
    latency: ExecutionLatencyRecord | None = None,
) -> ExecutionObservation:
    return ExecutionObservation(
        result=result,
        expected_price=expected_price,
        latency=latency
        or ExecutionLatencyRecord(
            submitted_at=NOW,
            acknowledged_at=NOW + timedelta(milliseconds=100),
            completed_at=NOW + timedelta(milliseconds=500),
        ),
        source_refs={"execution": "fixture:quality"},
    )


def _approved_intent(quantity: Decimal) -> OrderIntent:
    order_id = UUID("00000000-0000-0000-0000-000000000041")
    signal = Signal(
        source="fixture-strategy",
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        generated_at=NOW,
        direction=SignalDirection.BUY,
        confidence=Decimal("0.60"),
        inputs_ref="fixture:features:041",
        rationale="fixture signal",
    )
    decision = RiskDecision(
        order_intent_id=order_id,
        status=RiskDecisionStatus.APPROVED,
        checks=(RiskCheck("fixture-risk", True, "risk approved"),),
        evaluated_at=NOW,
        policy_version="stage-022.fixture",
        rationale="fixture approved",
        max_position_size=Decimal("1"),
    )
    return OrderIntent(
        id=order_id,
        pair=signal.pair,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=quantity,
        created_at=NOW,
        signal=signal,
        risk_decision=decision,
        status=OrderStatus.RISK_APPROVED,
    )
