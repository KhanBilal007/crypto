"""Operator dashboard metric snapshots for continuous analytics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from abtp.analytics.performance import (
    PerformanceObservation,
    PerformanceWindowKind,
    PerformanceWindowReport,
    build_standard_performance_reports,
)
from abtp.analytics.trends import (
    ComparisonRow,
    TrendReport,
    build_ai_accuracy_trend,
    build_drawdown_trend,
    build_execution_trend,
    build_risk_trend,
    compare_regimes,
    compare_strategies,
)
from abtp.data.normalization import normalize_timestamp
from abtp.data.quality import DataQualityStatus, DataTrustLevel
from abtp.domain.models import JsonValue


@dataclass(frozen=True, slots=True)
class DashboardMetric:
    """One operator-facing metric value."""

    key: str
    value: str
    source_ref: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("dashboard metric key is required")
        if not self.source_ref.strip():
            raise ValueError("dashboard metric source_ref is required")

    def as_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "value": self.value,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class OperatorDashboardMetrics:
    """Read-only continuous performance metrics for operator dashboards."""

    generated_at: datetime
    performance_reports: tuple[PerformanceWindowReport, ...]
    strategy_comparison: tuple[ComparisonRow, ...]
    regime_comparison: tuple[ComparisonRow, ...]
    ai_accuracy_trend: TrendReport
    risk_trend: TrendReport
    drawdown_trend: TrendReport
    execution_trend: TrendReport
    metrics: tuple[DashboardMetric, ...]
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Dashboard analytics are read-only.",
        "Dashboard metrics cannot add controls, approve risk, create orders, or execute trades.",
        "Operators must review costs, drawdown, risk breaches, and execution quality together.",
        "No profit is guaranteed by performance analytics.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if not self.performance_reports:
            raise ValueError("dashboard metrics require performance reports")
        if not self.metrics:
            raise ValueError("dashboard metrics require metric values")
        if not self.limitations:
            raise ValueError("dashboard metric limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "performance_reports": [report.as_dict() for report in self.performance_reports],
            "strategy_comparison": [row.as_dict() for row in self.strategy_comparison],
            "regime_comparison": [row.as_dict() for row in self.regime_comparison],
            "ai_accuracy_trend": self.ai_accuracy_trend.as_dict(),
            "risk_trend": self.risk_trend.as_dict(),
            "drawdown_trend": self.drawdown_trend.as_dict(),
            "execution_trend": self.execution_trend.as_dict(),
            "metrics": [metric.as_dict() for metric in self.metrics],
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "report_count": str(len(self.performance_reports)),
            "strategy_count": str(len(self.strategy_comparison)),
            "regime_count": str(len(self.regime_comparison)),
            "metric_count": str(len(self.metrics)),
            "quality": self.quality.trust_level.value,
            "quality_flags": "|".join(self.quality.flags),
        }

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("dashboard analytics cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("dashboard analytics cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("dashboard analytics cannot submit orders")

    def apply_strategy_change(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("dashboard analytics cannot apply strategy changes")


def build_operator_dashboard_metrics(
    observations: Sequence[PerformanceObservation],
    *,
    generated_at: datetime,
) -> OperatorDashboardMetrics:
    """Build a deterministic read-only operator analytics snapshot."""

    reports = build_standard_performance_reports(observations, generated_at=generated_at)
    strategy_rows = compare_strategies(observations)
    regime_rows = compare_regimes(observations)
    ai_trend = build_ai_accuracy_trend(observations, generated_at=generated_at)
    risk_trend = build_risk_trend(observations, generated_at=generated_at)
    drawdown_trend = build_drawdown_trend(observations, generated_at=generated_at)
    execution_trend = build_execution_trend(observations, generated_at=generated_at)
    quality = _dashboard_quality(
        reports=reports,
        trends=(ai_trend, risk_trend, drawdown_trend, execution_trend),
        generated_at=generated_at,
    )
    return OperatorDashboardMetrics(
        generated_at=generated_at,
        performance_reports=reports,
        strategy_comparison=strategy_rows,
        regime_comparison=regime_rows,
        ai_accuracy_trend=ai_trend,
        risk_trend=risk_trend,
        drawdown_trend=drawdown_trend,
        execution_trend=execution_trend,
        metrics=_metrics(reports, strategy_rows, regime_rows),
        quality=quality,
        source_refs={"analytics": "continuous_performance"},
    )


def _metrics(
    reports: tuple[PerformanceWindowReport, ...],
    strategy_rows: tuple[ComparisonRow, ...],
    regime_rows: tuple[ComparisonRow, ...],
) -> tuple[DashboardMetric, ...]:
    by_kind = {report.window.kind: report for report in reports}
    daily = by_kind[PerformanceWindowKind.DAILY]
    weekly = by_kind[PerformanceWindowKind.WEEKLY]
    monthly = by_kind[PerformanceWindowKind.MONTHLY]
    long_term = by_kind[PerformanceWindowKind.LONG_TERM]
    best_strategy = strategy_rows[0].label if strategy_rows else "unavailable"
    best_regime = regime_rows[0].label if regime_rows else "unavailable"
    return (
        DashboardMetric("daily_net_return", str(daily.net_return), "analytics:daily"),
        DashboardMetric("weekly_net_return", str(weekly.net_return), "analytics:weekly"),
        DashboardMetric("monthly_net_return", str(monthly.net_return), "analytics:monthly"),
        DashboardMetric("long_term_net_return", str(long_term.net_return), "analytics:long_term"),
        DashboardMetric("max_drawdown", str(long_term.max_drawdown), "analytics:drawdown"),
        DashboardMetric("risk_breaches", str(long_term.risk_breach_count), "analytics:risk"),
        DashboardMetric("total_fees", str(long_term.total_fees), "analytics:costs"),
        DashboardMetric(
            "average_slippage_bps",
            str(long_term.average_slippage_bps),
            "analytics:execution",
        ),
        DashboardMetric("best_strategy", best_strategy, "analytics:strategy"),
        DashboardMetric("best_regime", best_regime, "analytics:regime"),
    )


def _dashboard_quality(
    *,
    reports: tuple[PerformanceWindowReport, ...],
    trends: tuple[TrendReport, ...],
    generated_at: datetime,
) -> DataQualityStatus:
    issues = tuple(
        [
            *(issue for report in reports for issue in report.quality.issues),
            *(issue for trend in trends for issue in trend.quality.issues),
        ]
    )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust = DataTrustLevel.REJECTED
    elif issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=issues,
        source_ref="analytics:dashboard",
        checked_at=generated_at,
    )
