from __future__ import annotations

from datetime import UTC, datetime

from abtp.notifications import (
    AlertCategory,
    AlertSeverity,
    DeliveryStatus,
    InMemoryNotificationChannel,
    NotificationAlert,
)
from abtp.observability import REDACTED_VALUE

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_in_memory_channel_sends_alert_and_redacts_secret_context() -> None:
    channel = InMemoryNotificationChannel("fixture")
    alert = NotificationAlert(
        category=AlertCategory.RISK_HALT,
        severity=AlertSeverity.CRITICAL,
        title="Risk halt active",
        message="drawdown breach",
        occurred_at=NOW,
        context={"api_key": "do-not-leak", "drawdown_pct": "0.12"},
    )

    delivery = channel.send(alert, sent_at=NOW)

    assert delivery.status is DeliveryStatus.SENT
    assert channel.alerts == (alert,)
    assert channel.alerts[0].context["api_key"] == REDACTED_VALUE
    assert "do-not-leak" not in str(channel.alerts[0].as_dict())


def test_in_memory_channel_can_fail_deterministically() -> None:
    channel = InMemoryNotificationChannel("failing", fail=True)
    alert = NotificationAlert(
        category=AlertCategory.EXCHANGE_OUTAGE,
        severity=AlertSeverity.CRITICAL,
        title="Exchange data feed disconnected",
        message="fixture feed disconnected",
        occurred_at=NOW,
        context={"exchange": "fixture"},
    )

    delivery = channel.send(alert, sent_at=NOW)

    assert delivery.status is DeliveryStatus.FAILED
    assert delivery.reason == "deterministic channel failure"
    assert not channel.alerts
