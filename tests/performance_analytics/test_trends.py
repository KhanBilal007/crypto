from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.analytics import (
    PerformanceObservation,
    TrendMetric,
    build_ai_accuracy_trend,
    build_drawdown_trend,
    build_execution_trend,
    build_risk_trend,
    compare_regimes,
    compare_strategies,
)

NOW = datetime(2026, 1, 7, 15, tzinfo=UTC)


def test_strategy_and_regime_comparisons_are_ranked_by_net_return() -> None:
    observations = _observations()
    strategies = compare_strategies(observations)
    regimes = compare_regimes(observations)

    assert strategies[0].label == "beta"
    assert strategies[0].net_return == Decimal("0.0097")
    assert strategies[1].label == "alpha"
    assert strategies[1].risk_breach_count == 1

    assert regimes[0].label == "trend_up"
    assert regimes[0].trade_count == 3
    assert regimes[1].label == "range_bound"


def test_ai_risk_drawdown_and_execution_trends_are_deterministic() -> None:
    observations = _observations()
    ai = build_ai_accuracy_trend(observations, generated_at=NOW)
    risk = build_risk_trend(observations, generated_at=NOW)
    drawdown = build_drawdown_trend(observations, generated_at=NOW)
    execution = build_execution_trend(observations, generated_at=NOW)

    assert ai.metric is TrendMetric.AI_ACCURACY
    assert ai.points[-1].period == "2026-01-07"
    assert ai.points[-1].value == Decimal("1.0000")
    assert risk.points[1].value == Decimal("1.0000")
    assert drawdown.points[1].value == Decimal("0.0000")
    assert execution.points[-1].value == Decimal("0.9000")
    assert execution.quality.is_trusted


def test_empty_trend_fails_closed() -> None:
    report = build_ai_accuracy_trend((), generated_at=NOW)

    assert report.quality.is_rejected
    assert report.points == ()
    assert "analytics_ai_accuracy_missing_points" in report.quality.flags


def test_trend_report_has_no_trading_or_strategy_authority() -> None:
    report = build_execution_trend(_observations(), generated_at=NOW)

    with pytest.raises(ValueError, match="cannot create order intents"):
        report.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()
    with pytest.raises(ValueError, match="cannot apply strategy changes"):
        report.apply_strategy_change()


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
