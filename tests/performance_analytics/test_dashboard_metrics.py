from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.analytics import (
    DashboardMetric,
    PerformanceObservation,
    build_operator_dashboard_metrics,
)

NOW = datetime(2026, 1, 7, 15, tzinfo=UTC)


def test_operator_dashboard_metrics_expose_read_only_summary_values() -> None:
    dashboard = build_operator_dashboard_metrics(_observations(), generated_at=NOW)
    metrics = {metric.key: metric.value for metric in dashboard.metrics}

    assert metrics["daily_net_return"] == "0.0097"
    assert metrics["weekly_net_return"] == "0.0196"
    assert metrics["monthly_net_return"] == "0.0196"
    assert metrics["long_term_net_return"] == "0.0196"
    assert metrics["risk_breaches"] == "1"
    assert metrics["best_strategy"] == "beta"
    assert metrics["best_regime"] == "trend_up"
    assert dashboard.quality.is_degraded
    assert dashboard.audit_payload()["metric_count"] == "10"
    assert dashboard.as_dict()["quality"] == "degraded"


def test_dashboard_metric_validates_required_fields() -> None:
    with pytest.raises(ValueError, match="dashboard metric key is required"):
        DashboardMetric("", "1", "fixture:metric")


def test_dashboard_metrics_have_no_trading_or_strategy_authority() -> None:
    dashboard = build_operator_dashboard_metrics(_observations(), generated_at=NOW)

    with pytest.raises(ValueError, match="cannot create order intents"):
        dashboard.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        dashboard.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        dashboard.submit_order()
    with pytest.raises(ValueError, match="cannot apply strategy changes"):
        dashboard.apply_strategy_change()


def test_public_imports_are_available() -> None:
    from abtp.analytics import OperatorDashboardMetrics, PerformanceWindowReport, TrendReport

    assert OperatorDashboardMetrics is not None
    assert PerformanceWindowReport is not None
    assert TrendReport is not None


def _observations() -> tuple[PerformanceObservation, ...]:
    return (
        _observation("2026-01-05T10:00:00+00:00", "alpha", "trend_up", "1020", "20", True, "0.90"),
        _observation(
            "2026-01-06T10:00:00+00:00",
            "alpha",
            "range_bound",
            "1010",
            "-10",
            False,
            "0.80",
            risk_breach_count=1,
        ),
        _observation("2026-01-07T10:00:00+00:00", "beta", "trend_up", "1030", "20", True, "0.95"),
        _observation("2026-01-07T12:00:00+00:00", "beta", "trend_up", "1040", "10", True, "0.85"),
    )


def _observation(
    observed_at: str,
    strategy_name: str,
    regime_label: str,
    equity: str,
    realized_pnl: str,
    prediction_correct: bool,
    execution_quality_score: str,
    *,
    risk_breach_count: int = 0,
) -> PerformanceObservation:
    return PerformanceObservation(
        observed_at=datetime.fromisoformat(observed_at),
        strategy_name=strategy_name,
        regime_label=regime_label,
        equity=Decimal(equity),
        realized_pnl=Decimal(realized_pnl),
        fees_paid=Decimal("1"),
        slippage_bps=Decimal("5"),
        trade_count=1,
        risk_breach_count=risk_breach_count,
        prediction_correct=prediction_correct,
        execution_quality_score=Decimal(execution_quality_score),
        source_refs={observed_at: f"fixture:{observed_at}"},
    )
