from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection, IntegrityError
from uuid import UUID

import pytest

from abtp.audit import DecisionAuditRecorder, build_audit_event, build_paper_cycle_audit_events
from abtp.data import OrderBookMetrics, StreamHealth
from abtp.domain import Asset, AssetPair, AuditEventType, Candle, Exchange
from abtp.observability import InMemoryStructuredLogger, log_blocked_decision
from abtp.paper import PaperMarketSnapshot, PaperTradingConfig, PaperTradingEngine
from abtp.repositories import AuditRepository
from abtp.strategies import MinRiskSpotStrategyV1

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PAIR = AssetPair(Asset("BTC"), Asset("USDT"))
CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000029")


def test_paper_cycle_audit_events_reconstruct_blocked_decision(
    migrated_connection: Connection,
) -> None:
    engine = PaperTradingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=PaperTradingConfig(timeframe="1h"),
    )
    cycle = engine.on_market_update(_snapshot(0, Decimal("100"), stale=True))
    recorder = DecisionAuditRecorder(AuditRepository(migrated_connection))

    event_ids = recorder.append_many(
        build_paper_cycle_audit_events(cycle, correlation_id=CORRELATION_ID)
    )
    trail = recorder.reconstruct(str(CORRELATION_ID))

    assert len(event_ids) == 4
    assert trail.blocked_trade_reasons == ("live data is stale",)
    assert "market_input" in trail.as_dict()["event_types"]
    assert "blocked_trade" in trail.as_dict()["event_types"]


def test_audit_persistence_is_append_only(migrated_connection: Connection) -> None:
    recorder = DecisionAuditRecorder(AuditRepository(migrated_connection))
    event_id = recorder.append(
        build_audit_event(
            event_type=AuditEventType.RISK_DECISION,
            occurred_at=NOW,
            payload={"status": "rejected", "reasons": "fixture risk reject"},
            correlation_id=CORRELATION_ID,
        )
    )

    with pytest.raises(IntegrityError, match="append-only"):
        migrated_connection.execute(
            "UPDATE audit_events SET event_type = 'changed' WHERE id = ?",
            (event_id,),
        )


def test_audit_builder_rejects_secret_like_payload_keys_without_value_leakage() -> None:
    with pytest.raises(ValueError) as exc_info:
        build_audit_event(
            event_type=AuditEventType.MARKET_INPUT,
            occurred_at=NOW,
            payload={"api_key": "do-not-leak"},
        )

    assert "api_key" in str(exc_info.value)
    assert "do-not-leak" not in str(exc_info.value)


def test_logs_and_audit_together_capture_risk_rejection_reason(
    migrated_connection: Connection,
) -> None:
    recorder = DecisionAuditRecorder(AuditRepository(migrated_connection))
    logger = InMemoryStructuredLogger()

    recorder.append(
        build_audit_event(
            event_type=AuditEventType.RISK_DECISION,
            occurred_at=NOW,
            payload={
                "status": "rejected",
                "risk_rejection_reasons": "drawdown breach|excessive spread",
            },
            correlation_id=CORRELATION_ID,
        )
    )
    log_blocked_decision(
        logger,
        occurred_at=NOW,
        component="risk",
        reason="drawdown breach",
        correlation_id=str(CORRELATION_ID),
    )

    trail = recorder.reconstruct(str(CORRELATION_ID))

    assert trail.risk_rejection_reasons == ("drawdown breach", "excessive spread")
    assert logger.by_correlation(str(CORRELATION_ID))[0].message == "drawdown breach"


def _snapshot(
    index: int,
    close: Decimal,
    *,
    stale: bool = False,
) -> PaperMarketSnapshot:
    candle = _candle(index, close)
    received_at = candle.closed_at + timedelta(seconds=1)
    return PaperMarketSnapshot(
        candle=candle,
        order_book_metrics=OrderBookMetrics(
            best_bid=candle.close - Decimal("0.01"),
            best_ask=candle.close + Decimal("0.01"),
            spread=Decimal("0.02"),
            bid_depth=Decimal("5"),
            ask_depth=Decimal("4"),
            imbalance=Decimal("0.1111111111111111111111111111"),
        ),
        health=StreamHealth(
            is_connected=not stale,
            is_stale=stale,
            is_degraded=stale,
            disconnect_count=1 if stale else 0,
            last_message_at=received_at,
            latency_ms=10,
            stale_after=timedelta(seconds=30),
        ),
        received_at=received_at,
    )


def _candle(index: int, close: Decimal) -> Candle:
    opened_at = NOW + timedelta(hours=index)
    return Candle(
        exchange=Exchange("fixture"),
        pair=PAIR,
        interval="1h",
        opened_at=opened_at,
        closed_at=opened_at + timedelta(hours=1),
        open=close,
        high=close * Decimal("1.005"),
        low=close * Decimal("0.995"),
        close=close,
        volume=Decimal("1"),
    )
