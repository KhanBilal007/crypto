from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.backtesting import PerformanceMetrics, RegimePerformance
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.validation import (
    RobustnessPolicy,
    TimeSeriesSplitPolicy,
    WalkForwardValidationEngine,
    WalkForwardValidationRequest,
    WindowMetricResult,
    rolling_window_splits,
    score_robustness,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_walk_forward_report_accepts_stable_out_of_sample_strategy() -> None:
    results = _window_results(
        "trend-v1",
        oos_returns=(Decimal("0.04"), Decimal("0.03"), Decimal("0.02")),
        parameters=(Decimal("12"), Decimal("12"), Decimal("13")),
    )
    report = WalkForwardValidationEngine().validate(
        WalkForwardValidationRequest(
            strategy_name="trend-v1",
            window_results=results,
            required_regime="trend_up",
            generated_at=NOW,
            source_refs={"backtest": "fixture:walk_forward"},
        )
    )

    assert report.accepted_for_promotion
    assert report.robustness.pass_ratio == Decimal("1")
    assert report.robustness.regime_coverage["trend_up"] == 9
    assert report.audit_payload()["strategy_name"] == "trend-v1"
    assert report.as_dict()["accepted_for_promotion"] is True


def test_overfit_gap_rejects_strategy_even_when_training_was_strong() -> None:
    results = _window_results(
        "overfit-v1",
        train_returns=(Decimal("0.35"), Decimal("0.34"), Decimal("0.36")),
        oos_returns=(Decimal("0.01"), Decimal("0.00"), Decimal("-0.01")),
    )
    score = score_robustness(
        results,
        policy=RobustnessPolicy(max_train_test_return_gap=Decimal("0.10")),
        generated_at=NOW,
    )

    assert not score.accepted_for_promotion
    assert "train/test performance gap suggests overfitting" in score.rejected_reasons
    assert score.quality.is_degraded


def test_fragile_out_of_sample_windows_reject_promotion() -> None:
    results = _window_results(
        "fragile-v1",
        oos_returns=(Decimal("0.04"), Decimal("-0.03"), Decimal("-0.02")),
        drawdowns=(Decimal("0.04"), Decimal("0.18"), Decimal("0.08")),
    )
    report = WalkForwardValidationEngine().validate(
        WalkForwardValidationRequest(
            strategy_name="fragile-v1",
            window_results=results,
            generated_at=NOW,
        )
    )

    assert not report.accepted_for_promotion
    assert "out-of-sample pass ratio is below threshold" in report.rejected_reasons
    assert "out-of-sample drawdown exceeds limit" in report.rejected_reasons


def test_required_regime_coverage_is_enforced() -> None:
    results = _window_results(
        "range-v1",
        regime_label="range_bound",
        oos_returns=(Decimal("0.03"), Decimal("0.02"), Decimal("0.03")),
    )
    score = score_robustness(results, required_regime="trend_up", generated_at=NOW)

    assert not score.accepted_for_promotion
    assert "required regime has insufficient out-of-sample coverage" in score.rejected_reasons


def test_rejected_quality_fails_closed() -> None:
    rejected_quality = DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="bad_fixture",
                severity=DataTrustLevel.REJECTED,
                reason="rejected validation fixture",
            ),
        ),
        source_ref="fixture:quality",
        checked_at=NOW,
    )
    results = _window_results(
        "quality-v1",
        oos_returns=(Decimal("0.03"), Decimal("0.03"), Decimal("0.03")),
        quality=rejected_quality,
    )
    score = score_robustness(results, generated_at=NOW)

    assert not score.accepted_for_promotion
    assert score.quality.is_rejected
    assert "validation window quality is not trusted" in score.rejected_reasons


def test_engine_has_no_signal_or_order_authority() -> None:
    engine = WalkForwardValidationEngine()

    with pytest.raises(ValueError, match="cannot create strategy signals"):
        engine.create_signal(object())
    with pytest.raises(ValueError, match="cannot submit orders"):
        engine.submit_order(object())


def test_public_imports_are_available() -> None:
    import abtp.validation as validation

    assert validation.WalkForwardValidationEngine is WalkForwardValidationEngine


def _window_results(
    strategy_name: str,
    *,
    train_returns: tuple[Decimal, Decimal, Decimal] = (
        Decimal("0.06"),
        Decimal("0.05"),
        Decimal("0.04"),
    ),
    oos_returns: tuple[Decimal, Decimal, Decimal],
    drawdowns: tuple[Decimal, Decimal, Decimal] = (
        Decimal("0.04"),
        Decimal("0.05"),
        Decimal("0.04"),
    ),
    parameters: tuple[Decimal, Decimal, Decimal] = (
        Decimal("12"),
        Decimal("12"),
        Decimal("12"),
    ),
    regime_label: str = "trend_up",
    quality: DataQualityStatus | None = None,
) -> tuple[WindowMetricResult, ...]:
    windows = rolling_window_splits(
        tuple(NOW + timedelta(days=index) for index in range(9)),
        TimeSeriesSplitPolicy(train_size=3, test_size=1, step_size=2),
    )
    return tuple(
        WindowMetricResult(
            strategy_name=strategy_name,
            window=window,
            in_sample_metrics=_metrics(
                net_return=train_returns[index],
                max_drawdown=Decimal("0.03"),
                regime_label=regime_label,
            ),
            out_of_sample_metrics=_metrics(
                net_return=oos_returns[index],
                max_drawdown=drawdowns[index],
                regime_label=regime_label,
            ),
            parameters={"lookback": parameters[index]},
            quality=quality,
            source_refs={"window": f"fixture:window:{index}"},
        )
        for index, window in enumerate(windows)
    )


def _metrics(
    *,
    net_return: Decimal,
    max_drawdown: Decimal,
    regime_label: str,
) -> PerformanceMetrics:
    return PerformanceMetrics(
        net_return=net_return,
        max_drawdown=max_drawdown,
        profit_factor=Decimal("1.5") if net_return >= Decimal("0") else Decimal("0.8"),
        sharpe_ratio=Decimal("1.0"),
        sortino_ratio=Decimal("1.1"),
        win_rate=Decimal("0.60") if net_return >= Decimal("0") else Decimal("0.35"),
        expectancy=net_return / Decimal("3"),
        average_win=Decimal("0.03"),
        average_loss=Decimal("-0.01"),
        exposure_time_pct=Decimal("0.40"),
        tail_loss=Decimal("-0.02") if max_drawdown <= Decimal("0.15") else Decimal("-0.07"),
        total_fees=Decimal("1"),
        trade_count=10,
        costs_included=True,
        regime_performance=(
            RegimePerformance(
                regime_label=regime_label,
                period_count=3,
                net_return=net_return,
                max_drawdown=max_drawdown,
                win_rate=Decimal("0.60") if net_return >= Decimal("0") else Decimal("0.35"),
                expectancy=net_return / Decimal("3"),
            ),
        ),
    )
