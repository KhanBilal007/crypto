from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.data import OrderBookMetrics, StreamHealth
from abtp.protection import (
    CrashProtectionConfig,
    MarketProtectionSnapshot,
    ProtectiveAction,
    ProtectiveActionType,
    RecoveryStatus,
    evaluate_market_protection,
    evaluate_recovery,
)
from abtp.protection.recovery import recovery_progress_score

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_destructive_protective_actions_cannot_auto_execute() -> None:
    with pytest.raises(ValueError, match="cannot auto-execute"):
        ProtectiveAction(
            action_type=ProtectiveActionType.CANCEL_PENDING_ORDERS,
            reason="fixture cancel request",
            requested_at=NOW,
            priority=1,
            can_execute_automatically=True,
        )


def test_recovery_requires_healthy_snapshots_and_manual_approval() -> None:
    previous = evaluate_market_protection(_snapshot(price_return_pct=Decimal("-0.12")))
    config = CrashProtectionConfig(severe_condition_count=2)

    waiting = evaluate_recovery(
        (_snapshot(), _snapshot(observed_at=NOW + timedelta(minutes=1))),
        previous_decision=previous,
        config=config,
        manual_approval=False,
    )

    assert waiting.status is RecoveryStatus.MANUAL_APPROVAL_REQUIRED
    assert not waiting.can_resume
    assert waiting.manual_approval_required
    assert waiting.action_plan.block_new_trades

    approved = evaluate_recovery(
        (_snapshot(), _snapshot(observed_at=NOW + timedelta(minutes=1))),
        previous_decision=previous,
        config=config,
        manual_approval=True,
    )

    assert approved.status is RecoveryStatus.ELIGIBLE_FOR_GRADUAL_RESUME
    assert approved.can_resume
    assert approved.gradual_resume
    assert recovery_progress_score(approved) == Decimal("1")


def test_recovery_stays_blocked_while_crash_conditions_remain_active() -> None:
    previous = evaluate_market_protection(_snapshot(price_return_pct=Decimal("-0.12")))
    decision = evaluate_recovery(
        (
            _snapshot(price_return_pct=Decimal("-0.09")),
            _snapshot(observed_at=NOW + timedelta(minutes=1)),
        ),
        previous_decision=previous,
        config=CrashProtectionConfig(severe_condition_count=2),
        manual_approval=True,
    )

    assert decision.status is RecoveryStatus.BLOCKED
    assert not decision.can_resume
    assert "crash conditions are still active" in decision.reasons
    with pytest.raises(RuntimeError, match="crash conditions"):
        decision.require_resume_allowed()


def test_public_imports_are_available() -> None:
    import abtp.protection as protection

    assert protection.CrashProtectionConfig is CrashProtectionConfig
    assert protection.ProtectiveActionType.PAUSE_TRADING.value == "pause_trading"


def _snapshot(
    *,
    observed_at: datetime = NOW,
    price_return_pct: Decimal = Decimal("0.01"),
) -> MarketProtectionSnapshot:
    return MarketProtectionSnapshot(
        observed_at=observed_at,
        exchange_name="fixture",
        price_return_pct=price_return_pct,
        realized_volatility_pct=Decimal("0.01"),
        order_book_metrics=OrderBookMetrics(
            best_bid=Decimal("99.99"),
            best_ask=Decimal("100.01"),
            spread=Decimal("0.02"),
            bid_depth=Decimal("5"),
            ask_depth=Decimal("5"),
            imbalance=Decimal("0"),
        ),
        stream_health=StreamHealth(
            is_connected=True,
            is_stale=False,
            is_degraded=False,
            disconnect_count=0,
            last_message_at=observed_at,
            latency_ms=10,
            stale_after=timedelta(seconds=30),
        ),
    )
