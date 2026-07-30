from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.backtesting import PerformanceMetrics, RegimePerformance
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.lab import (
    StrategyBenchmarkInput,
    StrategyCatalogueEntry,
    StrategyCatalogueStatus,
    compare_strategies,
    regime_benchmark_score,
)
from abtp.validation import RobustnessScore

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_benchmark_comparison_recommends_best_walk_forward_candidate() -> None:
    report = compare_strategies(
        (
            _input(
                "baseline-v1",
                status=StrategyCatalogueStatus.BENCHMARK,
                net_return=Decimal("0.04"),
            ),
            _input("trend-v1", net_return=Decimal("0.18"), robustness_score=Decimal("0.85")),
            _input("weak-v1", net_return=Decimal("0.02"), robustness_score=Decimal("0.50")),
        ),
        baseline_key="baseline-v1",
        regime_label="trend_up",
        generated_at=NOW,
        source_refs={"walk_forward": "fixture:stage-039"},
    )

    assert report.recommended_strategy_key == "trend-v1"
    assert report.results[0].strategy_key == "trend-v1"
    assert report.results[0].eligible
    assert report.results[0].baseline_delta > Decimal("0")
    assert report.audit_payload()["recommended_strategy_key"] == "trend-v1"


def test_disabled_strategy_is_ranked_but_not_eligible() -> None:
    report = compare_strategies(
        (
            _input(
                "baseline-v1",
                status=StrategyCatalogueStatus.BENCHMARK,
                net_return=Decimal("0.04"),
            ),
            _input(
                "disabled-v1",
                status=StrategyCatalogueStatus.DISABLED,
                net_return=Decimal("0.30"),
                robustness_score=Decimal("0.95"),
            ),
            _input("trend-v1", net_return=Decimal("0.30"), robustness_score=Decimal("0.90")),
        ),
        baseline_key="baseline-v1",
        regime_label="trend_up",
        generated_at=NOW,
    )

    disabled = next(result for result in report.results if result.strategy_key == "disabled-v1")
    assert not disabled.eligible
    assert "strategy is disabled in laboratory catalogue" in disabled.rejected_reasons
    assert report.recommended_strategy_key == "trend-v1"


def test_missing_walk_forward_evidence_rejects_candidate() -> None:
    report = compare_strategies(
        (
            _input(
                "baseline-v1",
                status=StrategyCatalogueStatus.BENCHMARK,
                net_return=Decimal("0.04"),
            ),
            _input("trend-v1", net_return=Decimal("0.18"), robustness_score=None),
        ),
        baseline_key="baseline-v1",
        regime_label="trend_up",
        generated_at=NOW,
    )

    trend = next(result for result in report.results if result.strategy_key == "trend-v1")
    assert not trend.eligible
    assert "walk-forward validation evidence is required" in trend.rejected_reasons


def test_regime_specific_score_uses_matching_regime_performance() -> None:
    metrics = _metrics(
        net_return=Decimal("0.10"),
        regime_label="range_bound",
        regime_win_rate=Decimal("0.75"),
    )

    assert regime_benchmark_score(metrics, "range_bound") > regime_benchmark_score(
        metrics, "trend_up"
    )


def test_rejected_quality_fails_closed() -> None:
    rejected_quality = DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="bad_lab_fixture",
                severity=DataTrustLevel.REJECTED,
                reason="rejected lab fixture",
            ),
        ),
        source_ref="fixture:lab_quality",
        checked_at=NOW,
    )
    report = compare_strategies(
        (
            _input(
                "baseline-v1",
                status=StrategyCatalogueStatus.BENCHMARK,
                net_return=Decimal("0.04"),
            ),
            _input(
                "trend-v1",
                net_return=Decimal("0.18"),
                robustness_score=Decimal("0.85"),
                quality=rejected_quality,
            ),
        ),
        baseline_key="baseline-v1",
        regime_label="trend_up",
        generated_at=NOW,
    )

    trend = next(result for result in report.results if result.strategy_key == "trend-v1")
    assert not trend.eligible
    assert trend.quality.is_rejected
    assert "benchmark input quality is not trusted" in trend.rejected_reasons


def test_laboratory_report_has_no_signal_or_order_authority() -> None:
    report = compare_strategies(
        (
            _input(
                "baseline-v1",
                status=StrategyCatalogueStatus.BENCHMARK,
                net_return=Decimal("0.04"),
            ),
            _input("trend-v1", net_return=Decimal("0.18"), robustness_score=Decimal("0.85")),
        ),
        baseline_key="baseline-v1",
        regime_label="trend_up",
        generated_at=NOW,
    )

    with pytest.raises(ValueError, match="cannot create strategy signals"):
        report.create_signal(object())
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order(object())


def test_public_imports_are_available() -> None:
    import abtp.lab as lab

    assert lab.compare_strategies is compare_strategies


def _input(
    key: str,
    *,
    status: StrategyCatalogueStatus = StrategyCatalogueStatus.CANDIDATE,
    net_return: Decimal,
    robustness_score: Decimal | None = Decimal("0.75"),
    quality: DataQualityStatus | None = None,
) -> StrategyBenchmarkInput:
    entry = StrategyCatalogueEntry(
        key=key,
        name=key,
        version="1.0",
        family="trend",
        status=status,
        regime_suitability=("trend_up",),
        created_at=NOW,
        source_refs={"strategy": f"fixture:{key}"},
    )
    return StrategyBenchmarkInput(
        entry=entry,
        metrics=_metrics(net_return=net_return, regime_label="trend_up"),
        measured_at=NOW,
        robustness=(_robustness(key, robustness_score) if robustness_score is not None else None),
        quality=quality,
        source_refs={"metrics": f"fixture:metrics:{key}"},
    )


def _metrics(
    *,
    net_return: Decimal,
    regime_label: str,
    regime_win_rate: Decimal = Decimal("0.65"),
) -> PerformanceMetrics:
    return PerformanceMetrics(
        net_return=net_return,
        max_drawdown=Decimal("0.04"),
        profit_factor=Decimal("1.8"),
        sharpe_ratio=Decimal("1.1"),
        sortino_ratio=Decimal("1.3"),
        win_rate=Decimal("0.62"),
        expectancy=net_return / Decimal("10"),
        average_win=Decimal("0.03"),
        average_loss=Decimal("-0.01"),
        exposure_time_pct=Decimal("0.40"),
        tail_loss=Decimal("-0.02"),
        total_fees=Decimal("1"),
        trade_count=20,
        costs_included=True,
        regime_performance=(
            RegimePerformance(
                regime_label=regime_label,
                period_count=10,
                net_return=net_return,
                max_drawdown=Decimal("0.03"),
                win_rate=regime_win_rate,
                expectancy=net_return / Decimal("10"),
            ),
        ),
    )


def _robustness(strategy_name: str, score: Decimal) -> RobustnessScore:
    return RobustnessScore(
        strategy_name=strategy_name,
        total_score=score,
        pass_ratio=Decimal("1"),
        average_out_of_sample_return=Decimal("0.03"),
        worst_out_of_sample_drawdown=Decimal("0.04"),
        average_train_test_return_gap=Decimal("0.02"),
        parameter_stability_score=Decimal("0.9"),
        regime_coverage={"trend_up": 10},
        accepted_for_promotion=True,
        rejected_reasons=(),
        evidence=(f"strategy={strategy_name}", "fixture=lab"),
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref=f"fixture:robustness:{strategy_name}",
            checked_at=NOW,
        ),
        policy_version="stage-039.v1",
        generated_at=NOW,
    )
