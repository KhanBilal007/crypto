from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection
from uuid import UUID

import pytest

from abtp.audit import DecisionAuditRecorder, build_audit_event
from abtp.data import (
    DataQualityIssue,
    DataQualityStatus,
    DataTrustLevel,
    OrderBookMetrics,
    StreamHealth,
)
from abtp.protection import (
    CrashCondition,
    MarketProtectionSnapshot,
    ProtectiveActionType,
    evaluate_market_protection,
)
from abtp.repositories import AuditRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)
CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000037")


def test_simulated_crash_blocks_new_trades_and_requests_protection_actions() -> None:
    decision = evaluate_market_protection(
        _snapshot(
            price_return_pct=Decimal("-0.12"),
            realized_volatility_pct=Decimal("0.08"),
            pending_order_count=2,
        )
    )

    assert decision.protection_active
    assert decision.block_new_trades
    assert decision.quality.is_rejected
    assert [detection.condition for detection in decision.detections] == [
        CrashCondition.FLASH_CRASH,
        CrashCondition.ABNORMAL_VOLATILITY,
    ]
    action_types = tuple(action.action_type for action in decision.action_plan.actions)
    assert ProtectiveActionType.BLOCK_NEW_ENTRIES in action_types
    assert ProtectiveActionType.CANCEL_PENDING_ORDERS in action_types
    assert ProtectiveActionType.ENABLE_KILL_SWITCH in action_types
    with pytest.raises(RuntimeError, match="flash crash"):
        decision.require_trading_allowed()


def test_stale_outage_high_spread_liquidity_and_api_failures_fail_safe() -> None:
    decision = evaluate_market_protection(
        _snapshot(
            order_book_metrics=OrderBookMetrics(
                best_bid=Decimal("99"),
                best_ask=Decimal("101"),
                spread=Decimal("2"),
                bid_depth=Decimal("0.1"),
                ask_depth=Decimal("0.1"),
                imbalance=Decimal("0"),
            ),
            stream_health=StreamHealth(
                is_connected=False,
                is_stale=True,
                is_degraded=True,
                disconnect_count=2,
                last_message_at=NOW - timedelta(minutes=10),
                latency_ms=9000,
                stale_after=timedelta(seconds=30),
            ),
            api_failure=True,
        )
    )

    conditions = {detection.condition for detection in decision.detections}

    assert CrashCondition.EXCHANGE_OUTAGE in conditions
    assert CrashCondition.STALE_DATA in conditions
    assert CrashCondition.HIGH_SPREAD in conditions
    assert CrashCondition.LIQUIDITY_COLLAPSE in conditions
    assert CrashCondition.API_FAILURE in conditions
    assert decision.action_plan.block_new_trades
    assert "exchange API failure reported" in decision.reasons


def test_rejected_data_quality_is_protection_condition() -> None:
    decision = evaluate_market_protection(
        _snapshot(
            data_quality=DataQualityStatus(
                trust_level=DataTrustLevel.REJECTED,
                issues=(
                    DataQualityIssue(
                        flag="stale_data",
                        severity=DataTrustLevel.REJECTED,
                        reason="fixture rejected data",
                    ),
                ),
                source_ref="fixture:data",
                checked_at=NOW,
            )
        )
    )

    assert decision.protection_active
    assert decision.detections[0].condition is CrashCondition.REJECTED_DATA_QUALITY
    assert "protection_rejected_data_quality" in decision.quality.flags


def test_protection_audit_payload_can_be_recorded(migrated_connection: Connection) -> None:
    decision = evaluate_market_protection(_snapshot(price_return_pct=Decimal("-0.10")))
    recorder = DecisionAuditRecorder(AuditRepository(migrated_connection))

    recorder.append(
        build_audit_event(
            event_type="market_crash_protection",
            occurred_at=NOW,
            payload=decision.audit_payload(),
            correlation_id=CORRELATION_ID,
        )
    )
    trail = recorder.reconstruct(str(CORRELATION_ID))

    assert trail.events[0].payload["block_new_trades"] == "True"
    assert trail.events[0].payload["conditions"] == "flash_crash"
    assert "block_new_entries" in trail.events[0].payload["action_types"]


def test_safe_snapshot_does_not_activate_protection() -> None:
    decision = evaluate_market_protection(_snapshot())

    assert not decision.protection_active
    assert not decision.block_new_trades
    assert decision.quality.is_trusted
    assert decision.action_plan.actions == ()


def _snapshot(
    *,
    price_return_pct: Decimal = Decimal("0.01"),
    realized_volatility_pct: Decimal = Decimal("0.01"),
    order_book_metrics: OrderBookMetrics | None = None,
    stream_health: StreamHealth | None = None,
    data_quality: DataQualityStatus | None = None,
    api_failure: bool = False,
    pending_order_count: int = 0,
) -> MarketProtectionSnapshot:
    return MarketProtectionSnapshot(
        observed_at=NOW,
        exchange_name="fixture",
        price_return_pct=price_return_pct,
        realized_volatility_pct=realized_volatility_pct,
        order_book_metrics=order_book_metrics
        or OrderBookMetrics(
            best_bid=Decimal("99.99"),
            best_ask=Decimal("100.01"),
            spread=Decimal("0.02"),
            bid_depth=Decimal("5"),
            ask_depth=Decimal("5"),
            imbalance=Decimal("0"),
        ),
        stream_health=stream_health
        or StreamHealth(
            is_connected=True,
            is_stale=False,
            is_degraded=False,
            disconnect_count=0,
            last_message_at=NOW,
            latency_ms=10,
            stale_after=timedelta(seconds=30),
        ),
        data_quality=data_quality,
        api_failure=api_failure,
        pending_order_count=pending_order_count,
        source_refs={"fixture": "market"},
    )
