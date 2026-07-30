from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.analytics import (
    PerformanceObservation,
    PerformanceWindowKind,
    build_performance_window_report,
    build_standard_performance_reports,
    daily_window,
)

NOW = datetime(2026, 1, 7, 15, tzinfo=UTC)


def test_daily_weekly_monthly_and_long_term_reports_are_deterministic() -> None:
    reports = build_standard_performance_reports(_observations(), generated_at=NOW)
    by_kind = {report.window.kind: report for report in reports}

    daily = by_kind[PerformanceWindowKind.DAILY]
    weekly = by_kind[PerformanceWindowKind.WEEKLY]
    monthly = by_kind[PerformanceWindowKind.MONTHLY]
    long_term = by_kind[PerformanceWindowKind.LONG_TERM]

    assert daily.observation_count == 2
    assert daily.net_pnl == Decimal("30")
    assert daily.net_return == Decimal("0.0097")
    assert daily.total_fees == Decimal("2")
    assert daily.average_slippage_bps == Decimal("5.0000")
    assert daily.prediction_accuracy == Decimal("1.0000")
    assert daily.average_execution_quality == Decimal("0.9000")
    assert daily.quality.is_trusted

    assert weekly.observation_count == 4
    assert weekly.net_return == Decimal("0.0196")
    assert weekly.risk_breach_count == 1
    assert weekly.quality.is_degraded

    assert monthly.observation_count == 5
    assert monthly.trade_count == 4
    assert long_term.observation_count == 5
    assert long_term.audit_payload()["window"] == "long_term"


def test_empty_window_report_fails_closed_with_clear_quality() -> None:
    report = build_performance_window_report(
        _observations(),
        window=daily_window(datetime(2026, 1, 3, 12, tzinfo=UTC)),
        generated_at=NOW,
    )

    assert report.observation_count == 0
    assert report.quality.is_rejected
    assert report.net_return == Decimal("0")
    assert "analytics_missing_observations" in report.quality.flags


def test_performance_report_has_no_trading_or_strategy_authority() -> None:
    report = build_standard_performance_reports(_observations(), generated_at=NOW)[0]

    with pytest.raises(ValueError, match="cannot create order intents"):
        report.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()
    with pytest.raises(ValueError, match="cannot apply strategy changes"):
        report.apply_strategy_change()


def test_observation_validates_cost_and_quality_inputs() -> None:
    with pytest.raises(ValueError, match="fees_paid cannot be negative"):
        PerformanceObservation(
            observed_at=NOW,
            strategy_name="alpha",
            regime_label="trend_up",
            equity=Decimal("1000"),
            realized_pnl=Decimal("0"),
            fees_paid=Decimal("-1"),
            slippage_bps=Decimal("0"),
        )


def _observations() -> tuple[PerformanceObservation, ...]:
    return (
        PerformanceObservation(
            observed_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
            strategy_name="alpha",
            regime_label="trend_up",
            equity=Decimal("1000"),
            realized_pnl=Decimal("0"),
            fees_paid=Decimal("0"),
            slippage_bps=Decimal("0"),
            source_refs={"jan1": "fixture:jan1"},
        ),
        PerformanceObservation(
            observed_at=datetime(2026, 1, 5, 10, tzinfo=UTC),
            strategy_name="alpha",
            regime_label="trend_up",
            equity=Decimal("1020"),
            realized_pnl=Decimal("20"),
            fees_paid=Decimal("1"),
            slippage_bps=Decimal("5"),
            trade_count=1,
            prediction_correct=True,
            execution_quality_score=Decimal("0.90"),
            source_refs={"jan5": "fixture:jan5"},
        ),
        PerformanceObservation(
            observed_at=datetime(2026, 1, 6, 10, tzinfo=UTC),
            strategy_name="alpha",
            regime_label="range_bound",
            equity=Decimal("1010"),
            realized_pnl=Decimal("-10"),
            fees_paid=Decimal("1"),
            slippage_bps=Decimal("7"),
            trade_count=1,
            risk_breach_count=1,
            prediction_correct=False,
            execution_quality_score=Decimal("0.80"),
            source_refs={"jan6": "fixture:jan6"},
        ),
        PerformanceObservation(
            observed_at=datetime(2026, 1, 7, 10, tzinfo=UTC),
            strategy_name="beta",
            regime_label="trend_up",
            equity=Decimal("1030"),
            realized_pnl=Decimal("20"),
            fees_paid=Decimal("1"),
            slippage_bps=Decimal("4"),
            trade_count=1,
            prediction_correct=True,
            execution_quality_score=Decimal("0.95"),
            source_refs={"jan7a": "fixture:jan7a"},
        ),
        PerformanceObservation(
            observed_at=datetime(2026, 1, 7, 12, tzinfo=UTC),
            strategy_name="beta",
            regime_label="trend_up",
            equity=Decimal("1040"),
            realized_pnl=Decimal("10"),
            fees_paid=Decimal("1"),
            slippage_bps=Decimal("6"),
            trade_count=1,
            prediction_correct=True,
            execution_quality_score=Decimal("0.85"),
            source_refs={"jan7b": "fixture:jan7b"},
        ),
    )
