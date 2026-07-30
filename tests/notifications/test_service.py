from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.api import PaperParameterHealth, PaperPortfolioStatus, PaperStatusResponse
from abtp.data import StreamHealth
from abtp.notifications import (
    AlertCategory,
    AlertSeverity,
    AlertThrottleConfig,
    DeliveryStatus,
    InMemoryNotificationChannel,
    NotificationService,
)
from abtp.observability import InMemoryStructuredLogger, LogLevel

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_notification_service_dispatches_paper_kill_switch_alert() -> None:
    channel = InMemoryNotificationChannel("fixture")
    service = NotificationService((channel,))
    alert = service.alert_from_paper_status(
        _status(kill_switch_active=True, blocked_reason="kill switch active: manual stop"),
        occurred_at=NOW,
    )

    assert alert is not None
    result = service.dispatch(alert, sent_at=NOW)

    assert alert.category is AlertCategory.KILL_SWITCH
    assert alert.severity is AlertSeverity.CRITICAL
    assert result.delivered
    assert result.trading_permitted
    assert channel.alerts[0].message == "kill switch active: manual stop"


def test_alert_throttling_suppresses_duplicate_alerts() -> None:
    channel = InMemoryNotificationChannel("fixture")
    service = NotificationService(
        (channel,),
        throttle=AlertThrottleConfig(window=timedelta(minutes=10)),
    )
    alert = service.risk_halt_alert(
        reason="drawdown breach",
        occurred_at=NOW,
        drawdown_pct=Decimal("0.12"),
    )

    first = service.dispatch(alert, sent_at=NOW)
    second = service.dispatch(alert, sent_at=NOW + timedelta(minutes=1))

    assert first.delivered
    assert second.suppressed
    assert second.deliveries[0].status is DeliveryStatus.SUPPRESSED
    assert len(channel.alerts) == 1


def test_critical_live_mode_alert_failure_fails_closed() -> None:
    channel = InMemoryNotificationChannel("failing", fail=True)
    logger = InMemoryStructuredLogger()
    service = NotificationService((channel,), logger=logger)
    alert = service.risk_halt_alert(reason="risk halt", occurred_at=NOW)

    result = service.dispatch(alert, sent_at=NOW, live_mode_event=True)

    assert not result.delivered
    assert not result.trading_permitted
    with pytest.raises(RuntimeError, match="trading must remain blocked"):
        result.require_trading_permitted()
    assert logger.records[0].level is LogLevel.CRITICAL
    assert logger.records[0].fields["trading_permitted"] is False


def test_noncritical_failure_does_not_claim_trading_permission_block() -> None:
    channel = InMemoryNotificationChannel("failing", fail=True)
    service = NotificationService((channel,))
    alert = service.manual_approval_alert(
        title="Paper review",
        message="manual review requested",
        occurred_at=NOW,
        order_preview_ref="paper:preview:1",
    )

    result = service.dispatch(alert, sent_at=NOW, live_mode_event=False)

    assert alert.category is AlertCategory.MANUAL_APPROVAL_REQUEST
    assert result.trading_permitted
    assert result.deliveries[0].status is DeliveryStatus.FAILED


def test_stream_health_creates_exchange_outage_alert() -> None:
    service = NotificationService((InMemoryNotificationChannel("fixture"),))

    alert = service.alert_from_stream_health(
        StreamHealth(
            is_connected=False,
            is_stale=True,
            is_degraded=True,
            disconnect_count=2,
            last_message_at=NOW,
            latency_ms=5000,
            stale_after=timedelta(seconds=30),
        ),
        occurred_at=NOW,
        exchange_name="sandbox",
    )

    assert alert is not None
    assert alert.category is AlertCategory.EXCHANGE_OUTAGE
    assert alert.severity is AlertSeverity.CRITICAL
    assert alert.context["disconnect_count"] == 2


def test_no_alert_for_unblocked_healthy_paper_status() -> None:
    service = NotificationService((InMemoryNotificationChannel("fixture"),))

    assert service.alert_from_paper_status(_status(), occurred_at=NOW) is None


def _status(
    *,
    kill_switch_active: bool = False,
    paused: bool = False,
    blocked_reason: str = "not blocked",
    data_health: str = "healthy",
) -> PaperStatusResponse:
    return PaperStatusResponse(
        current_btc_price=Decimal("100"),
        active_regime="trend_up",
        latest_signal="buy",
        latest_risk_decision="approved",
        blocked_reason=blocked_reason,
        data_health=data_health,
        portfolio=PaperPortfolioStatus(
            cash=Decimal("10000"),
            base_quantity=Decimal("0"),
            average_entry_price=Decimal("0"),
            realized_pnl=Decimal("0"),
            fees_paid=Decimal("0"),
            equity=Decimal("10000"),
            drawdown_pct=Decimal("0"),
        ),
        parameter_health=(
            PaperParameterHealth(
                key="market.close",
                value="100",
                status="trusted",
                reason="fixture",
            ),
        ),
        paused=paused,
        kill_switch_active=kill_switch_active,
        cycles_count=1,
        trades_count=0,
        updated_at=NOW,
    )
