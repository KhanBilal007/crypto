from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from abtp.backtesting import (
    AcceptanceGate,
    PerformanceMetrics,
    RegimePerformance,
    build_performance_report,
    evaluate_acceptance,
)

GENERATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def test_report_rejects_positive_return_when_drawdown_fails() -> None:
    metrics = _metrics(net_return=Decimal("0.22"), max_drawdown=Decimal("0.30"))

    report = build_performance_report(
        metrics,
        strategy_name="fixture_strategy",
        gate=AcceptanceGate(max_drawdown=Decimal("0.10")),
        generated_at=GENERATED_AT,
    )

    assert not report.eligible_for_paper_trading
    drawdown_check = next(
        check for check in report.acceptance_checks if check.name == "max_drawdown"
    )
    assert not drawdown_check.passed
    assert "even if net return is positive" in drawdown_check.reason


def test_report_serializes_snapshot_without_plain_decimal_objects() -> None:
    report = build_performance_report(
        _metrics(),
        strategy_name="fixture_strategy",
        generated_at=GENERATED_AT,
        source_refs={"backtest": "fixture:run:1"},
    )

    snapshot = report.as_dict()

    assert snapshot["strategy_name"] == "fixture_strategy"
    assert snapshot["generated_at"] == "2026-01-01T00:00:00+00:00"
    assert snapshot["eligible_for_paper_trading"] is True
    assert snapshot["metrics"]["net_return"] == "0.10"  # type: ignore[index]
    assert snapshot["source_refs"] == {"backtest": "fixture:run:1"}


def test_report_includes_regime_performance_slices() -> None:
    report = build_performance_report(
        _metrics(
            regime_performance=(
                RegimePerformance(
                    regime_label="trend_up",
                    period_count=3,
                    net_return=Decimal("0.08"),
                    max_drawdown=Decimal("0.01"),
                    win_rate=Decimal("0.67"),
                    expectancy=Decimal("0.02"),
                ),
            )
        ),
        strategy_name="fixture_strategy",
        generated_at=GENERATED_AT,
    )

    snapshot = report.as_dict()

    assert snapshot["metrics"]["regime_performance"][0]["regime_label"] == "trend_up"  # type: ignore[index]


def test_acceptance_gate_requires_costs_and_minimum_trade_sample() -> None:
    checks = evaluate_acceptance(
        _metrics(costs_included=False, trade_count=0),
        AcceptanceGate(min_trade_count=1, require_costs_included=True),
    )

    failed = {check.name for check in checks if not check.passed}

    assert failed == {"costs_included", "trade_count"}


def test_public_imports_are_available() -> None:
    report = build_performance_report(_metrics(), strategy_name="fixture_strategy")

    assert report.metrics.profit_factor == Decimal("1.5")


def _metrics(
    *,
    net_return: Decimal = Decimal("0.10"),
    max_drawdown: Decimal = Decimal("0.03"),
    costs_included: bool = True,
    trade_count: int = 3,
    regime_performance: tuple[RegimePerformance, ...] = (),
) -> PerformanceMetrics:
    return PerformanceMetrics(
        net_return=net_return,
        max_drawdown=max_drawdown,
        profit_factor=Decimal("1.5"),
        sharpe_ratio=Decimal("0.8"),
        sortino_ratio=Decimal("1.1"),
        win_rate=Decimal("0.6"),
        expectancy=Decimal("0.02"),
        average_win=Decimal("0.04"),
        average_loss=Decimal("-0.02"),
        exposure_time_pct=Decimal("0.4"),
        tail_loss=Decimal("-0.02"),
        total_fees=Decimal("1.23"),
        trade_count=trade_count,
        costs_included=costs_included,
        regime_performance=regime_performance,
    )
