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
from abtp.exchanges.health import (
    ExchangeHealthInput,
    ExchangeHealthPolicy,
    ExchangeHealthStatus,
    score_exchange_health,
)
from abtp.exchanges.permission_gates import TradingPermission
from abtp.exchanges.reliability import ReliabilityInput, score_reliability

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_exchange_health_scores_healthy_supplied_evidence() -> None:
    health = score_exchange_health(_health_input())

    assert health.status is ExchangeHealthStatus.HEALTHY
    assert health.score == Decimal("1.0000")
    assert health.spread_bps == Decimal("10.0000")
    assert health.permission_gate.permission is TradingPermission.READ_ONLY
    assert not health.permission_gate.block_new_entries
    assert health.audit_payload()["permission"] == "read_only"


def test_high_spread_and_thin_liquidity_pause_trading_permission() -> None:
    health = score_exchange_health(
        _health_input(
            metrics=OrderBookMetrics(
                best_bid=Decimal("100"),
                best_ask=Decimal("110"),
                spread=Decimal("10"),
                bid_depth=Decimal("0.20"),
                ask_depth=Decimal("0.25"),
                imbalance=Decimal("0.10"),
            )
        )
    )

    assert health.status is ExchangeHealthStatus.UNAVAILABLE
    assert health.quality.is_rejected
    assert health.permission_gate.permission is TradingPermission.PAUSE_TRADING
    assert health.permission_gate.block_new_entries
    assert health.permission_gate.manual_review_required
    assert "order-book spread exceeds exchange health threshold" in health.rejection_reasons
    assert "liquidity depth is below exchange health threshold" in health.rejection_reasons


def test_stale_or_disconnected_heartbeat_blocks_new_entries() -> None:
    health = score_exchange_health(
        _health_input(
            stream=StreamHealth(
                is_connected=False,
                is_stale=True,
                is_degraded=True,
                disconnect_count=3,
                last_message_at=NOW - timedelta(minutes=5),
                latency_ms=3000,
                stale_after=timedelta(seconds=30),
            )
        )
    )

    assert health.status is ExchangeHealthStatus.UNAVAILABLE
    assert "stream heartbeat is disconnected" in health.rejection_reasons
    assert "stream heartbeat is stale" in health.rejection_reasons
    assert health.permission_gate.pause_trading


def test_reconciliation_blocker_requires_pause_and_manual_review() -> None:
    health = score_exchange_health(
        _health_input(
            reconciliation_blocked=True,
            reconciliation_quality=DataQualityStatus(
                trust_level=DataTrustLevel.REJECTED,
                issues=(
                    DataQualityIssue(
                        flag="reconciliation_order_mismatch",
                        severity=DataTrustLevel.REJECTED,
                        reason="open order mismatch",
                    ),
                ),
                source_ref="fixture:reconciliation",
                checked_at=NOW,
            ),
        )
    )

    assert health.quality.is_rejected
    assert health.permission_gate.pause_trading
    assert "exchange reconciliation blocks continuation" in health.rejection_reasons
    assert "reconciliation_quality" in health.source_refs


def test_missing_order_book_and_degraded_stream_mark_paper_only() -> None:
    health = score_exchange_health(
        _health_input(
            stream=StreamHealth(
                is_connected=True,
                is_stale=False,
                is_degraded=True,
                disconnect_count=0,
                last_message_at=NOW,
                latency_ms=1200,
                stale_after=timedelta(seconds=30),
            ),
            metrics=None,
        ),
        policy=ExchangeHealthPolicy(min_health_score=Decimal("0.80")),
    )

    assert health.status is ExchangeHealthStatus.DEGRADED
    assert health.quality.is_degraded
    assert health.permission_gate.permission is TradingPermission.PAPER_ONLY


def test_exchange_health_has_no_order_or_risk_authority() -> None:
    health = score_exchange_health(_health_input())

    with pytest.raises(ValueError, match="cannot submit orders"):
        health.submit_order()
    with pytest.raises(ValueError, match="cannot create order intents"):
        health.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        health.approve_risk()


def _health_input(
    *,
    stream: StreamHealth | None = None,
    metrics: OrderBookMetrics | None = None,
    reconciliation_blocked: bool = False,
    reconciliation_quality: DataQualityStatus | None = None,
) -> ExchangeHealthInput:
    return ExchangeHealthInput(
        exchange_name="sandbox",
        checked_at=NOW,
        reliability=score_reliability(
            ReliabilityInput(
                exchange_name="sandbox",
                observed_at=NOW,
                request_count=100,
                error_count=0,
                latency_ms_samples=(80, 90, 100),
                source_refs={"reliability": "fixture:reliability"},
            )
        ),
        stream_health=stream
        if stream is not None
        else StreamHealth(
            is_connected=True,
            is_stale=False,
            is_degraded=False,
            disconnect_count=0,
            last_message_at=NOW,
            latency_ms=100,
            stale_after=timedelta(seconds=30),
        ),
        order_book_metrics=metrics
        if metrics is not None
        else OrderBookMetrics(
            best_bid=Decimal("9995"),
            best_ask=Decimal("10005"),
            spread=Decimal("10"),
            bid_depth=Decimal("2.5"),
            ask_depth=Decimal("2.0"),
            imbalance=Decimal("0.11"),
        ),
        reconciliation_blocked=reconciliation_blocked,
        reconciliation_quality=reconciliation_quality,
        source_refs={"health": "fixture:health"},
    )
