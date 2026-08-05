"""In-memory monitoring metrics for deterministic ABTP stages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.api import PaperStatusResponse
from abtp.data import normalize_timestamp
from abtp.observability.logging import SENSITIVE_KEY_PARTS
from abtp.paper import PaperTradingCycleResult


class MetricKind(StrEnum):
    """Metric point type."""

    COUNTER = "counter"
    GAUGE = "gauge"


@dataclass(frozen=True, slots=True)
class MetricPoint:
    """One JSON-compatible metric observation."""

    name: str
    value: Decimal
    kind: MetricKind
    observed_at: datetime
    labels: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("metric name is required")
        if not self.value.is_finite():
            raise ValueError("metric value must be finite")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        labels = dict(self.labels or {})
        _ensure_safe_labels(labels)
        object.__setattr__(self, "labels", labels)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "value": str(self.value),
            "kind": self.kind.value,
            "observed_at": self.observed_at.isoformat(),
            "labels": dict(self.labels),
        }


class MetricsRegistry:
    """Deterministic in-memory metrics registry."""

    def __init__(self) -> None:
        self._points: list[MetricPoint] = []

    @property
    def points(self) -> tuple[MetricPoint, ...]:
        return tuple(self._points)

    def record(self, point: MetricPoint) -> MetricPoint:
        self._points.append(point)
        return point

    def counter(
        self,
        name: str,
        *,
        increment: Decimal = Decimal("1"),
        observed_at: datetime,
        labels: Mapping[str, str] | None = None,
    ) -> MetricPoint:
        if increment < Decimal("0"):
            raise ValueError("counter increment cannot be negative")
        return self.record(
            MetricPoint(
                name=name,
                value=increment,
                kind=MetricKind.COUNTER,
                observed_at=observed_at,
                labels=labels or {},
            )
        )

    def gauge(
        self,
        name: str,
        *,
        value: Decimal,
        observed_at: datetime,
        labels: Mapping[str, str] | None = None,
    ) -> MetricPoint:
        return self.record(
            MetricPoint(
                name=name,
                value=value,
                kind=MetricKind.GAUGE,
                observed_at=observed_at,
                labels=labels or {},
            )
        )

    def series(self, name: str) -> tuple[MetricPoint, ...]:
        return tuple(point for point in self.points if point.name == name)

    def latest(self, name: str) -> MetricPoint | None:
        series = self.series(name)
        return series[-1] if series else None


def record_paper_cycle_metrics(
    registry: MetricsRegistry,
    cycle: PaperTradingCycleResult,
) -> tuple[MetricPoint, ...]:
    """Record metrics for one paper decision cycle."""

    observed_at = cycle.snapshot.received_at
    labels = {
        "component": "paper",
        "data_health": cycle.snapshot.health.status,
        "regime": cycle.regime.label.value,
    }
    points = [
        registry.gauge(
            "abtp_data_latency_ms",
            value=Decimal(cycle.snapshot.health.latency_ms),
            observed_at=observed_at,
            labels=labels,
        ),
        registry.gauge(
            "abtp_paper_equity",
            value=cycle.equity,
            observed_at=observed_at,
            labels=labels,
        ),
    ]
    if cycle.strategy_evaluation is not None:
        points.append(
            registry.counter(
                "abtp_signal_count",
                observed_at=observed_at,
                labels={**labels, "direction": cycle.strategy_evaluation.signal.direction.value},
            )
        )
    if cycle.risk_decision_status == "rejected":
        points.append(
            registry.counter(
                "abtp_risk_reject_count",
                observed_at=observed_at,
                labels=labels,
            )
        )
    if cycle.execution_result is not None:
        points.append(
            registry.counter(
                "abtp_order_status_count",
                observed_at=observed_at,
                labels={**labels, "status": cycle.execution_result.status.value},
            )
        )
    if cycle.skipped_reason is not None:
        points.append(
            registry.counter(
                "abtp_blocked_trade_count",
                observed_at=observed_at,
                labels={**labels, "reason": cycle.skipped_reason},
            )
        )
    return tuple(points)


def record_paper_status_metrics(
    registry: MetricsRegistry,
    status: PaperStatusResponse,
) -> tuple[MetricPoint, ...]:
    """Record dashboard/API paper status metrics."""

    labels = {"component": "paper_api", "data_health": status.data_health}
    return (
        registry.gauge(
            "abtp_paper_equity",
            value=status.portfolio.equity,
            observed_at=status.updated_at,
            labels=labels,
        ),
        registry.gauge(
            "abtp_paper_drawdown_pct",
            value=status.portfolio.drawdown_pct,
            observed_at=status.updated_at,
            labels=labels,
        ),
        registry.gauge(
            "abtp_paper_realized_pnl",
            value=status.portfolio.realized_pnl,
            observed_at=status.updated_at,
            labels=labels,
        ),
        registry.counter(
            "abtp_risk_reject_count",
            increment=Decimal("1") if status.latest_risk_decision == "rejected" else Decimal("0"),
            observed_at=status.updated_at,
            labels=labels,
        ),
    )


def _ensure_safe_labels(labels: Mapping[str, str]) -> None:
    for key in labels:
        lowered = key.lower()
        if any(part in lowered for part in SENSITIVE_KEY_PARTS):
            raise ValueError(f"secret-like metric label is not allowed: {key}")
