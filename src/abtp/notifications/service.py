"""Alert generation, throttling, and fail-closed notification dispatch."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from abtp.api import PaperStatusResponse
from abtp.data import StreamHealth
from abtp.domain.models import JsonValue
from abtp.notifications.channels import (
    AlertCategory,
    AlertSeverity,
    DeliveryStatus,
    NotificationAlert,
    NotificationChannel,
    NotificationDelivery,
)
from abtp.observability import InMemoryStructuredLogger, LogLevel


@dataclass(frozen=True, slots=True)
class AlertThrottleConfig:
    """Alert throttling configuration."""

    window: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if self.window < timedelta(0):
            raise ValueError("throttle window cannot be negative")


@dataclass(frozen=True, slots=True)
class AlertDispatchResult:
    """Result of alert dispatch across channels."""

    alert: NotificationAlert
    deliveries: tuple[NotificationDelivery, ...]
    suppressed: bool
    trading_permitted: bool
    reason: str

    @property
    def delivered(self) -> bool:
        return any(delivery.status is DeliveryStatus.SENT for delivery in self.deliveries)

    def require_trading_permitted(self) -> None:
        """Fail closed when critical alert delivery did not succeed."""

        if not self.trading_permitted:
            raise RuntimeError(self.reason)


class NotificationService:
    """Deterministic alert service with throttling and fail-closed critical behavior."""

    def __init__(
        self,
        channels: Sequence[NotificationChannel],
        *,
        throttle: AlertThrottleConfig | None = None,
        logger: InMemoryStructuredLogger | None = None,
    ) -> None:
        if not channels:
            raise ValueError("at least one notification channel is required")
        self._channels = tuple(channels)
        self._throttle = throttle or AlertThrottleConfig()
        self._logger = logger
        self._last_sent_at_by_key: dict[str, datetime] = {}

    def dispatch(
        self,
        alert: NotificationAlert,
        *,
        sent_at: datetime,
        live_mode_event: bool = False,
    ) -> AlertDispatchResult:
        """Send one alert, applying throttle and critical fail-closed behavior."""

        if self._is_throttled(alert, sent_at):
            delivery = NotificationDelivery(
                alert_id=alert.id,
                channel_name="throttle",
                status=DeliveryStatus.SUPPRESSED,
                delivered_at=sent_at,
                reason="duplicate alert suppressed by throttle window",
            )
            result = AlertDispatchResult(
                alert=alert,
                deliveries=(delivery,),
                suppressed=True,
                trading_permitted=not _requires_success(alert, live_mode_event),
                reason=delivery.reason,
            )
            self._log_result(result, sent_at)
            return result

        deliveries = tuple(channel.send(alert, sent_at=sent_at) for channel in self._channels)
        delivered = any(delivery.status is DeliveryStatus.SENT for delivery in deliveries)
        if delivered:
            self._last_sent_at_by_key[alert.throttle_key] = sent_at
        requires_success = _requires_success(alert, live_mode_event)
        result = AlertDispatchResult(
            alert=alert,
            deliveries=deliveries,
            suppressed=False,
            trading_permitted=(delivered or not requires_success),
            reason=(
                "critical live-mode alert delivery failed; trading must remain blocked"
                if requires_success and not delivered
                else "alert dispatched"
            ),
        )
        self._log_result(result, sent_at)
        return result

    def alert_from_paper_status(
        self,
        status: PaperStatusResponse,
        *,
        occurred_at: datetime,
    ) -> NotificationAlert | None:
        """Build an alert from paper dashboard/API state when an operator should know."""

        if status.kill_switch_active:
            return _alert(
                AlertCategory.KILL_SWITCH,
                AlertSeverity.CRITICAL,
                "Kill switch active",
                status.blocked_reason,
                occurred_at,
                {
                    "drawdown_pct": str(status.portfolio.drawdown_pct),
                    "data_health": status.data_health,
                },
            )
        if status.paused:
            return _alert(
                AlertCategory.RISK_HALT,
                AlertSeverity.WARNING,
                "Paper trading paused",
                status.blocked_reason,
                occurred_at,
                {"data_health": status.data_health},
            )
        if status.data_health == "stale":
            return _alert(
                AlertCategory.STALE_DATA,
                AlertSeverity.CRITICAL,
                "Market data stale",
                status.blocked_reason,
                occurred_at,
                {"data_health": status.data_health},
            )
        if status.blocked_reason != "not blocked":
            return _alert(
                AlertCategory.BLOCKED_TRADE,
                AlertSeverity.WARNING,
                "Paper trade blocked",
                status.blocked_reason,
                occurred_at,
                {
                    "latest_signal": status.latest_signal,
                    "latest_risk_decision": status.latest_risk_decision,
                },
            )
        return None

    def alert_from_stream_health(
        self,
        health: StreamHealth,
        *,
        occurred_at: datetime,
        exchange_name: str,
    ) -> NotificationAlert | None:
        """Build an exchange/data-health alert."""

        if not health.is_connected:
            return _alert(
                AlertCategory.EXCHANGE_OUTAGE,
                AlertSeverity.CRITICAL,
                "Exchange data feed disconnected",
                f"{exchange_name} feed is disconnected",
                occurred_at,
                {"exchange": exchange_name, "disconnect_count": health.disconnect_count},
            )
        if health.is_stale:
            return _alert(
                AlertCategory.STALE_DATA,
                AlertSeverity.CRITICAL,
                "Market data stale",
                f"{exchange_name} feed is stale",
                occurred_at,
                {"exchange": exchange_name, "latency_ms": health.latency_ms},
            )
        return None

    def manual_approval_alert(
        self,
        *,
        title: str,
        message: str,
        occurred_at: datetime,
        order_preview_ref: str,
    ) -> NotificationAlert:
        """Create an explicit manual approval request alert."""

        return _alert(
            AlertCategory.MANUAL_APPROVAL_REQUEST,
            AlertSeverity.CRITICAL,
            title,
            message,
            occurred_at,
            {"order_preview_ref": order_preview_ref},
        )

    def risk_halt_alert(
        self,
        *,
        reason: str,
        occurred_at: datetime,
        drawdown_pct: Decimal | None = None,
    ) -> NotificationAlert:
        """Create a risk halt alert."""

        context: dict[str, JsonValue] = {}
        if drawdown_pct is not None:
            context["drawdown_pct"] = str(drawdown_pct)
        return _alert(
            AlertCategory.RISK_HALT,
            AlertSeverity.CRITICAL,
            "Risk halt active",
            reason,
            occurred_at,
            context,
        )

    def _is_throttled(self, alert: NotificationAlert, sent_at: datetime) -> bool:
        previous = self._last_sent_at_by_key.get(alert.throttle_key)
        return previous is not None and sent_at - previous < self._throttle.window

    def _log_result(self, result: AlertDispatchResult, sent_at: datetime) -> None:
        if self._logger is None:
            return
        level = LogLevel.WARNING if result.trading_permitted else LogLevel.CRITICAL
        self._logger.log(
            timestamp=sent_at,
            level=level,
            component="notifications",
            event="alert_dispatch",
            message=result.reason,
            fields={
                "alert_category": result.alert.category.value,
                "alert_severity": result.alert.severity.value,
                "delivered": result.delivered,
                "suppressed": result.suppressed,
                "trading_permitted": result.trading_permitted,
            },
            correlation_id=result.alert.correlation_id,
        )


def _requires_success(alert: NotificationAlert, live_mode_event: bool) -> bool:
    return live_mode_event and alert.severity is AlertSeverity.CRITICAL


def _alert(
    category: AlertCategory,
    severity: AlertSeverity,
    title: str,
    message: str,
    occurred_at: datetime,
    context: dict[str, JsonValue],
) -> NotificationAlert:
    return NotificationAlert(
        category=category,
        severity=severity,
        title=title,
        message=message,
        occurred_at=occurred_at,
        context=context,
    )
