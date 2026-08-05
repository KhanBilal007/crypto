"""Notification channel contracts and deterministic in-memory adapter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from abtp.data import normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.observability import redact_sensitive_fields


class AlertSeverity(StrEnum):
    """Alert severity consumed by operators and future risk controls."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertCategory(StrEnum):
    """Alert categories required by Stage 030."""

    RISK_HALT = "risk_halt"
    KILL_SWITCH = "kill_switch"
    EXCHANGE_OUTAGE = "exchange_outage"
    STALE_DATA = "stale_data"
    DRAWDOWN = "drawdown"
    LARGE_SLIPPAGE = "large_slippage"
    REPEATED_LOSSES = "repeated_losses"
    MANUAL_APPROVAL_REQUEST = "manual_approval_request"
    BLOCKED_TRADE = "blocked_trade"


class DeliveryStatus(StrEnum):
    """Notification delivery status."""

    SENT = "sent"
    SUPPRESSED = "suppressed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class NotificationAlert:
    """JSON-compatible notification request."""

    category: AlertCategory
    severity: AlertSeverity
    title: str
    message: str
    occurred_at: datetime
    context: Mapping[str, JsonValue]
    correlation_id: str | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_at", normalize_timestamp(self.occurred_at))
        if not self.title.strip():
            raise ValueError("alert title is required")
        if not self.message.strip():
            raise ValueError("alert message is required")
        object.__setattr__(self, "context", redact_sensitive_fields(self.context))

    @property
    def throttle_key(self) -> str:
        return f"{self.category.value}:{self.severity.value}:{self.title}"

    def as_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "occurred_at": self.occurred_at.isoformat(),
            "context": dict(self.context),
            "correlation_id": self.correlation_id,
        }


@dataclass(frozen=True, slots=True)
class NotificationDelivery:
    """Result from one channel delivery attempt."""

    alert_id: UUID
    channel_name: str
    status: DeliveryStatus
    delivered_at: datetime
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.channel_name.strip():
            raise ValueError("channel_name is required")
        object.__setattr__(self, "delivered_at", normalize_timestamp(self.delivered_at))


class NotificationChannel(Protocol):
    """Protocol for deterministic notification channel adapters."""

    @property
    def name(self) -> str:
        """Channel name."""

    def send(self, alert: NotificationAlert, *, sent_at: datetime) -> NotificationDelivery:
        """Send one alert."""


class InMemoryNotificationChannel:
    """Deterministic notification channel with optional failure mode."""

    def __init__(self, name: str = "memory", *, fail: bool = False) -> None:
        if not name.strip():
            raise ValueError("channel name is required")
        self._name = name
        self._fail = fail
        self._alerts: list[NotificationAlert] = []
        self._deliveries: list[NotificationDelivery] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def alerts(self) -> tuple[NotificationAlert, ...]:
        return tuple(self._alerts)

    @property
    def deliveries(self) -> tuple[NotificationDelivery, ...]:
        return tuple(self._deliveries)

    def send(self, alert: NotificationAlert, *, sent_at: datetime) -> NotificationDelivery:
        if self._fail:
            delivery = NotificationDelivery(
                alert_id=alert.id,
                channel_name=self.name,
                status=DeliveryStatus.FAILED,
                delivered_at=sent_at,
                reason="deterministic channel failure",
            )
            self._deliveries.append(delivery)
            return delivery
        self._alerts.append(alert)
        delivery = NotificationDelivery(
            alert_id=alert.id,
            channel_name=self.name,
            status=DeliveryStatus.SENT,
            delivered_at=sent_at,
        )
        self._deliveries.append(delivery)
        return delivery
