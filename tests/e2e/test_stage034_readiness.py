from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection
from uuid import UUID

from abtp.api import PaperAPIRequestContext, PaperAPIRole, PaperTradingAPI
from abtp.audit import DecisionAuditRecorder, build_audit_event, build_paper_cycle_audit_events
from abtp.config import load_settings
from abtp.dashboard import render_paper_dashboard
from abtp.data import OrderBookMetrics, StreamHealth
from abtp.db import apply_migrations, connect_database
from abtp.domain import (
    Asset,
    AssetPair,
    AuditEventType,
    Candle,
    Exchange,
    OrderIntent,
    OrderSide,
    OrderType,
    Signal,
    SignalDirection,
)
from abtp.live import LiveMarketPreflight, run_live_preflight
from abtp.notifications import InMemoryNotificationChannel, NotificationService
from abtp.observability import REDACTED_VALUE, MetricsRegistry, record_paper_cycle_metrics
from abtp.paper import PaperMarketSnapshot, PaperTradingConfig, PaperTradingEngine
from abtp.repositories import AuditRepository
from abtp.security import ExchangeKeyPermissions, mask_secret, validate_exchange_key_permissions
from abtp.strategies import MinRiskSpotStrategyV1

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PAIR = AssetPair(Asset("BTC"), Asset("USDT"))
CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000034")


def test_end_to_end_paper_flow_is_dashboarded_metered_and_auditable(
    migrated_connection: Connection,
) -> None:
    engine = PaperTradingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=PaperTradingConfig(timeframe="1h", order_quantity=Decimal("0.01")),
    )

    cycles = [
        engine.on_market_update(_snapshot(index, close))
        for index, close in enumerate(("100", "101", "102", "104"))
    ]
    latest = cycles[-1]

    assert any(cycle.executed for cycle in cycles)
    assert latest.risk_decision_status == "approved"
    assert engine.account.trades

    api = PaperTradingAPI(engine)
    context = PaperAPIRequestContext("stage034-operator", frozenset({PaperAPIRole.READ}))
    status = api.status(context)
    dashboard = render_paper_dashboard(status)

    assert status.cycles_count == 4
    assert status.trades_count >= 1
    assert "[Paper State]" in dashboard
    assert "Kill switch: False" in dashboard

    metrics = MetricsRegistry()
    points = record_paper_cycle_metrics(metrics, latest)

    assert points
    assert metrics.latest("abtp_paper_equity") is not None

    recorder = DecisionAuditRecorder(AuditRepository(migrated_connection))
    recorder.append_many(build_paper_cycle_audit_events(latest, correlation_id=CORRELATION_ID))
    trail = recorder.reconstruct(str(CORRELATION_ID))

    assert trail.as_dict()["event_count"] >= 5
    assert "risk_decision" in trail.as_dict()["event_types"]
    assert "order_intent" in trail.as_dict()["event_types"]


def test_risk_rejection_flow_blocks_live_preflight_without_adapter_submission() -> None:
    unsafe_intent = OrderIntent(
        pair=PAIR,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.0001"),
        created_at=NOW,
        signal=Signal(
            source="fixture",
            pair=PAIR,
            generated_at=NOW,
            direction=SignalDirection.BUY,
            confidence=Decimal("0.80"),
            inputs_ref="fixture:features",
            rationale="fixture signal for live preflight rejection smoke",
        ),
    )

    result = run_live_preflight(unsafe_intent, _live_market(), now=NOW)

    assert not result.allowed
    assert "order intent cannot bypass risk decision" in result.reasons
    assert result.preview.estimated_notional == Decimal("10.0000")


def test_dashboard_api_flow_and_notifications_surface_blocked_data() -> None:
    engine = PaperTradingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=PaperTradingConfig(timeframe="1h"),
    )
    engine.on_market_update(_snapshot(0, "100", stale=True))
    api = PaperTradingAPI(engine)
    context = PaperAPIRequestContext("stage034-viewer", frozenset({PaperAPIRole.READ}))
    status = api.status(context)

    assert status.data_health == "stale"
    assert status.blocked_reason == "live data is stale"

    channel = InMemoryNotificationChannel("stage034-memory")
    service = NotificationService((channel,))
    alert = service.alert_from_paper_status(status, occurred_at=NOW)

    assert alert is not None
    delivery = service.dispatch(alert, sent_at=NOW, live_mode_event=False)
    assert delivery.delivered
    assert channel.deliveries[0].alert_id == alert.id


def test_security_and_deployment_defaults_fail_closed() -> None:
    settings = load_settings({})

    assert settings.profile == "paper"
    assert settings.runtime.safe_mode
    assert not settings.runtime.can_execute_live
    assert not settings.live_trading_enabled
    assert mask_secret("stage034-secret") == REDACTED_VALUE

    permissions = ExchangeKeyPermissions.from_strings(
        exchange_name="fixture",
        scopes=("read", "trade", "withdraw"),
    )
    validation = validate_exchange_key_permissions(permissions)

    assert not validation.allowed
    assert any("withdraw" in reason for reason in validation.reasons)


def test_restore_drill_preserves_append_only_audit_reconstruction() -> None:
    source = connect_database(":memory:")
    restored = connect_database(":memory:")
    try:
        apply_migrations(source)
        recorder = DecisionAuditRecorder(AuditRepository(source))
        recorder.append(
            build_audit_event(
                event_type=AuditEventType.RISK_DECISION,
                occurred_at=NOW,
                payload={"status": "rejected", "reasons": "stage034 restore drill"},
                correlation_id=CORRELATION_ID,
            )
        )

        restored.executescript("\n".join(source.iterdump()))
        trail = DecisionAuditRecorder(AuditRepository(restored)).reconstruct(str(CORRELATION_ID))

        assert trail.as_dict()["event_count"] == 1
        assert trail.events[0].payload["reasons"] == "stage034 restore drill"
    finally:
        source.close()
        restored.close()


def _live_market() -> LiveMarketPreflight:
    return LiveMarketPreflight(
        price=Decimal("100000"),
        quote_balance_available=Decimal("1000"),
        account_equity=Decimal("10000"),
        fee_bps=Decimal("20"),
        spread_bps=Decimal("10"),
        slippage_bps=Decimal("5"),
        open_live_positions=0,
        permissions=ExchangeKeyPermissions.from_strings(
            exchange_name="fake-live",
            scopes=("read", "trade"),
            ip_allowlist=("203.0.113.10",),
        ),
        checked_at=NOW,
        account_checked_at=NOW,
    )


def _snapshot(index: int, close: str, *, stale: bool = False) -> PaperMarketSnapshot:
    candle = _candle(index, Decimal(close))
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
            latency_ms=2000 if stale else 10,
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
