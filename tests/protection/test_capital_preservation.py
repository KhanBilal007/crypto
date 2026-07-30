from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.data import (
    DataQualityIssue,
    DataQualityStatus,
    DataTrustLevel,
    OrderBookMetrics,
    StreamHealth,
)
from abtp.protection import (
    CapitalPreservationInput,
    EmergencyLevel,
    PreservationActionType,
    PreservationMode,
    evaluate_capital_preservation,
    evaluate_market_protection,
)
from abtp.protection.crash import MarketProtectionSnapshot
from abtp.protection.recovery import RecoveryStatus

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_safe_capital_preservation_context_allows_normal_mode() -> None:
    decision = evaluate_capital_preservation(_inputs())

    assert decision.protection_mode is PreservationMode.NORMAL
    assert decision.emergency_level is EmergencyLevel.NONE
    assert decision.recovery_status is RecoveryStatus.ELIGIBLE_FOR_GRADUAL_RESUME
    assert decision.preservation_score == Decimal("0.0740")
    assert decision.actions == ()
    assert not decision.block_new_trades
    assert decision.quality.is_trusted
    assert decision.audit_payload()["protection_mode"] == "normal"


def test_defensive_context_recommends_pause_reduce_cash_and_tighter_controls() -> None:
    decision = evaluate_capital_preservation(
        _inputs(
            crash_score=Decimal("0.50"),
            exchange_failure_score=Decimal("0.50"),
            liquidity_crisis_score=Decimal("0.60"),
            extreme_volatility_score=Decimal("0.55"),
            macro_shock_score=Decimal("0.60"),
            etf_outflow_score=Decimal("0.40"),
            current_cash_pct=Decimal("0.15"),
        )
    )

    action_types = {action.action_type for action in decision.actions}

    assert decision.protection_mode is PreservationMode.DEFENSIVE
    assert decision.emergency_level is EmergencyLevel.ELEVATED
    assert decision.recovery_status is RecoveryStatus.MANUAL_APPROVAL_REQUIRED
    assert decision.block_new_trades
    assert decision.target_cash_pct == Decimal("0.4000")
    assert decision.allocation_reduction_pct == Decimal("0.35")
    assert PreservationActionType.PAUSE_TRADING in action_types
    assert PreservationActionType.REDUCE_ALLOCATION in action_types
    assert PreservationActionType.INCREASE_CASH in action_types
    assert PreservationActionType.RAISE_CONFIDENCE_THRESHOLD in action_types
    assert PreservationActionType.TIGHTEN_STOPS in action_types
    assert decision.quality.is_degraded


def test_critical_context_recommends_kill_switch_review_without_auto_execution() -> None:
    decision = evaluate_capital_preservation(
        _inputs(
            crash_score=Decimal("0.90"),
            exchange_failure_score=Decimal("0.85"),
            liquidity_crisis_score=Decimal("0.80"),
            extreme_volatility_score=Decimal("0.90"),
            whale_dump_score=Decimal("0.70"),
            macro_shock_score=Decimal("0.75"),
            etf_outflow_score=Decimal("0.70"),
        )
    )

    kill_action = next(
        action
        for action in decision.actions
        if action.action_type is PreservationActionType.KILL_SWITCH_REVIEW
    )

    assert decision.protection_mode is PreservationMode.KILL_SWITCH_REVIEW
    assert decision.emergency_level is EmergencyLevel.CRITICAL
    assert decision.recovery_status is RecoveryStatus.BLOCKED
    assert decision.target_cash_pct == Decimal("0.6000")
    assert decision.allocation_reduction_pct == Decimal("0.75")
    assert decision.quality.is_rejected
    assert not kill_action.can_execute_automatically
    assert kill_action.requires_manual_review


def test_existing_crash_protection_decision_escalates_preservation_mode() -> None:
    crash_decision = evaluate_market_protection(
        MarketProtectionSnapshot(
            observed_at=NOW,
            exchange_name="fixture",
            price_return_pct=Decimal("-0.12"),
            realized_volatility_pct=Decimal("0.08"),
            order_book_metrics=_book(),
            stream_health=_health(),
        )
    )
    decision = evaluate_capital_preservation(_inputs(crash_decision=crash_decision))

    assert decision.protection_mode is PreservationMode.EMERGENCY
    assert decision.emergency_level is EmergencyLevel.SEVERE
    assert decision.block_new_trades
    assert "market crash protection blocks new trades" in decision.reasons


def test_stale_or_rejected_preservation_inputs_fail_closed() -> None:
    stale = evaluate_capital_preservation(_inputs(stale=True))
    rejected = evaluate_capital_preservation(_inputs(source_quality=_rejected_quality()))

    assert stale.protection_mode is PreservationMode.KILL_SWITCH_REVIEW
    assert stale.quality.is_rejected
    assert "capital preservation inputs are stale" in stale.reasons
    assert rejected.protection_mode is PreservationMode.KILL_SWITCH_REVIEW
    assert "capital preservation source quality is rejected" in rejected.reasons


def test_capital_preservation_input_validates_scores() -> None:
    with pytest.raises(ValueError, match="crash_score must be between 0 and 1"):
        _inputs(crash_score=Decimal("1.10"))


def test_capital_preservation_has_no_order_or_risk_authority() -> None:
    decision = evaluate_capital_preservation(
        _inputs(
            crash_score=Decimal("0.80"),
            exchange_failure_score=Decimal("0.75"),
            liquidity_crisis_score=Decimal("0.70"),
            extreme_volatility_score=Decimal("0.70"),
            macro_shock_score=Decimal("0.70"),
        )
    )

    with pytest.raises(ValueError, match="cannot create order intents"):
        decision.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        decision.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        decision.submit_order()
    with pytest.raises(RuntimeError, match="capital preservation"):
        decision.require_trading_allowed()


def test_public_imports_are_available() -> None:
    from abtp.protection import CapitalPreservationDecision, CapitalPreservationPolicy

    assert CapitalPreservationDecision is not None
    assert CapitalPreservationPolicy is not None


def _inputs(
    *,
    crash_score: Decimal = Decimal("0.10"),
    exchange_failure_score: Decimal = Decimal("0.05"),
    liquidity_crisis_score: Decimal = Decimal("0.05"),
    extreme_volatility_score: Decimal = Decimal("0.10"),
    whale_dump_score: Decimal = Decimal("0.05"),
    macro_shock_score: Decimal = Decimal("0.10"),
    etf_outflow_score: Decimal = Decimal("0.05"),
    current_cash_pct: Decimal = Decimal("0.30"),
    source_quality: DataQualityStatus | None = None,
    crash_decision=None,
    stale: bool = False,
) -> CapitalPreservationInput:
    return CapitalPreservationInput(
        observed_at=NOW,
        crash_score=crash_score,
        exchange_failure_score=exchange_failure_score,
        liquidity_crisis_score=liquidity_crisis_score,
        extreme_volatility_score=extreme_volatility_score,
        whale_dump_score=whale_dump_score,
        macro_shock_score=macro_shock_score,
        etf_outflow_score=etf_outflow_score,
        current_cash_pct=current_cash_pct,
        source_quality=source_quality or _trusted_quality(),
        crash_decision=crash_decision,
        source_refs={"capital_preservation": "fixture:capital_preservation"},
        stale=stale,
    )


def _book() -> OrderBookMetrics:
    return OrderBookMetrics(
        best_bid=Decimal("99.99"),
        best_ask=Decimal("100.01"),
        spread=Decimal("0.02"),
        bid_depth=Decimal("5"),
        ask_depth=Decimal("5"),
        imbalance=Decimal("0"),
    )


def _health() -> StreamHealth:
    return StreamHealth(
        is_connected=True,
        is_stale=False,
        is_degraded=False,
        disconnect_count=0,
        last_message_at=NOW - timedelta(seconds=1),
        latency_ms=10,
        stale_after=timedelta(seconds=30),
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:capital_preservation",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_capital_preservation_fixture",
                severity=DataTrustLevel.REJECTED,
                reason="capital preservation fixture rejected",
            ),
        ),
        source_ref="fixture:capital_preservation:rejected",
        checked_at=NOW,
    )
