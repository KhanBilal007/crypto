from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.domain import Asset, OrderStatus
from abtp.reconciliation import (
    BalanceRecord,
    ExchangeReconciliationEngine,
    FillRecord,
    OrderRecord,
    PositionRecord,
    ReconciliationEntity,
    ReconciliationRequest,
    ReconciliationSnapshot,
    RecoveryAction,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_matching_snapshots_can_resume_without_recovery_action() -> None:
    report = ExchangeReconciliationEngine().reconcile(
        ReconciliationRequest(
            database_snapshot=_snapshot("database"),
            exchange_snapshot=_snapshot("exchange"),
            checked_at=NOW,
        )
    )

    assert report.matched
    assert not report.blocks_continuation
    assert report.recovery_plan.can_resume
    assert report.recovery_plan.recommendations[0].action is RecoveryAction.NO_ACTION
    assert report.audit_payload()["mismatch_count"] == "0"


def test_balance_mismatch_blocks_continuation_and_requires_review() -> None:
    exchange = _snapshot(
        "exchange",
        balances=(
            BalanceRecord(Asset("BTC"), Decimal("0.90"), source_ref="exchange:BTC"),
            BalanceRecord(Asset("USDT"), Decimal("1000"), source_ref="exchange:USDT"),
        ),
    )

    report = ExchangeReconciliationEngine().reconcile(
        ReconciliationRequest(
            database_snapshot=_snapshot("database"),
            exchange_snapshot=exchange,
            checked_at=NOW,
        )
    )

    assert report.blocks_continuation
    assert report.quality.is_rejected
    assert any(mismatch.entity is ReconciliationEntity.BALANCE for mismatch in report.mismatches)
    assert RecoveryAction.RECONCILIATION_HOLD in {
        item.action for item in report.recovery_plan.recommendations
    }
    assert RecoveryAction.MANUAL_REVIEW in {
        item.action for item in report.recovery_plan.recommendations
    }


def test_position_order_and_fill_mismatches_are_explainable() -> None:
    exchange = _snapshot(
        "exchange",
        positions=(PositionRecord(Asset("BTC"), Decimal("0.80"), Decimal("80000")),),
        orders=(
            OrderRecord(
                order_intent_id="intent-1",
                exchange_order_id="exchange-1",
                status=OrderStatus.SUBMITTED,
                filled_quantity=Decimal("0"),
            ),
        ),
        fills=(
            FillRecord(
                order_intent_id="intent-1",
                exchange_order_id="exchange-1",
                filled_quantity=Decimal("0.50"),
                average_fill_price=Decimal("100000"),
            ),
        ),
    )

    report = ExchangeReconciliationEngine().reconcile(
        ReconciliationRequest(
            database_snapshot=_snapshot("database"),
            exchange_snapshot=exchange,
            checked_at=NOW,
        )
    )

    entities = {mismatch.entity for mismatch in report.mismatches}

    assert ReconciliationEntity.POSITION in entities
    assert ReconciliationEntity.ORDER in entities
    assert ReconciliationEntity.FILL in entities
    assert RecoveryAction.REPLAY_MISSING_FILL in {
        item.action for item in report.recovery_plan.recommendations
    }


def test_outage_stale_adapter_and_restart_marker_fail_safe() -> None:
    exchange = _snapshot(
        "exchange",
        adapter_stale=True,
        outage=True,
        restart_marker="restart-001",
    )

    report = ExchangeReconciliationEngine().reconcile(
        ReconciliationRequest(
            database_snapshot=_snapshot("database", restart_marker="restart-001"),
            exchange_snapshot=exchange,
            checked_at=NOW,
        )
    )

    actions = {item.action for item in report.recovery_plan.recommendations}

    assert RecoveryAction.API_OUTAGE_HOLD in actions
    assert RecoveryAction.REFRESH_EXCHANGE_STATE in actions
    assert RecoveryAction.RESTART_RECOVERY in actions
    assert report.recovery_plan.block_new_entries
    assert report.recovery_plan.manual_review_required


def test_report_has_no_execution_or_risk_authority() -> None:
    report = ExchangeReconciliationEngine().reconcile(
        ReconciliationRequest(
            database_snapshot=_snapshot("database"),
            exchange_snapshot=_snapshot("exchange"),
            checked_at=NOW,
        )
    )

    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()
    with pytest.raises(ValueError, match="cannot cancel orders"):
        report.cancel_order()
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk()


def _snapshot(
    source_name: str,
    *,
    balances: tuple[BalanceRecord, ...] | None = None,
    positions: tuple[PositionRecord, ...] | None = None,
    orders: tuple[OrderRecord, ...] | None = None,
    fills: tuple[FillRecord, ...] | None = None,
    adapter_stale: bool = False,
    outage: bool = False,
    restart_marker: str | None = None,
) -> ReconciliationSnapshot:
    return ReconciliationSnapshot(
        source_name=source_name,
        captured_at=NOW,
        balances=balances
        or (
            BalanceRecord(Asset("BTC"), Decimal("1.00"), source_ref=f"{source_name}:BTC"),
            BalanceRecord(Asset("USDT"), Decimal("1000"), source_ref=f"{source_name}:USDT"),
        ),
        positions=positions or (PositionRecord(Asset("BTC"), Decimal("1.00"), Decimal("100000")),),
        orders=orders
        or (
            OrderRecord(
                order_intent_id="intent-1",
                exchange_order_id="exchange-1",
                status=OrderStatus.FILLED,
                filled_quantity=Decimal("1.00"),
            ),
        ),
        fills=fills
        or (
            FillRecord(
                order_intent_id="intent-1",
                exchange_order_id="exchange-1",
                filled_quantity=Decimal("1.00"),
                average_fill_price=Decimal("100000"),
            ),
        ),
        adapter_stale=adapter_stale,
        outage=outage,
        restart_marker=restart_marker,
        source_refs={source_name: f"fixture:{source_name}"},
    )
