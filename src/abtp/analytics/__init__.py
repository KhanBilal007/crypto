"""Continuous performance analytics exports."""

from abtp.analytics.dashboard_metrics import (
    DashboardMetric,
    OperatorDashboardMetrics,
    build_operator_dashboard_metrics,
)
from abtp.analytics.performance import (
    PerformanceObservation,
    PerformanceWindow,
    PerformanceWindowKind,
    PerformanceWindowReport,
    build_performance_window_report,
    build_standard_performance_reports,
    daily_window,
    long_term_window,
    monthly_window,
    weekly_window,
)
from abtp.analytics.trends import (
    ComparisonRow,
    TrendMetric,
    TrendPoint,
    TrendReport,
    build_ai_accuracy_trend,
    build_drawdown_trend,
    build_execution_trend,
    build_risk_trend,
    compare_regimes,
    compare_strategies,
)

__all__ = [
    "ComparisonRow",
    "DashboardMetric",
    "OperatorDashboardMetrics",
    "PerformanceObservation",
    "PerformanceWindow",
    "PerformanceWindowKind",
    "PerformanceWindowReport",
    "TrendMetric",
    "TrendPoint",
    "TrendReport",
    "build_ai_accuracy_trend",
    "build_drawdown_trend",
    "build_execution_trend",
    "build_operator_dashboard_metrics",
    "build_performance_window_report",
    "build_risk_trend",
    "build_standard_performance_reports",
    "compare_regimes",
    "compare_strategies",
    "daily_window",
    "long_term_window",
    "monthly_window",
    "weekly_window",
]
