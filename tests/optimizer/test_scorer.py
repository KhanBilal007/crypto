from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from abtp.backtesting import PerformanceMetrics, RegimePerformance
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.optimizer import StrategyMetricSnapshot, StrategyScoringPolicy, score_strategies

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_strategy_scores_rank_deterministically_by_regime_fit() -> None:
    scores = score_strategies(
        (
            _snapshot("trend", win_rate=Decimal("0.70"), expectancy=Decimal("0.02")),
            _snapshot(
                "range",
                win_rate=Decimal("0.62"),
                expectancy=Decimal("0.015"),
                regime_label="range_bound",
            ),
        ),
        regime_label="trend_up",
    )

    assert [score.strategy_name for score in scores] == ["trend", "range"]
    assert scores[0].eligible
    assert scores[0].components["regime"] > scores[1].components["regime"]
    assert "regime=trend_up" in scores[0].evidence


def test_insufficient_sample_and_rejected_quality_fail_closed() -> None:
    scores = score_strategies(
        (
            _snapshot(
                "thin-sample",
                trade_count=1,
                quality=DataQualityStatus(
                    trust_level=DataTrustLevel.REJECTED,
                    issues=(
                        DataQualityIssue(
                            flag="bad_metrics",
                            severity=DataTrustLevel.REJECTED,
                            reason="fixture rejected metrics",
                        ),
                    ),
                    source_ref="fixture:metrics",
                    checked_at=NOW,
                ),
            ),
        ),
        regime_label="trend_up",
        policy=StrategyScoringPolicy(min_sample_size=5),
    )

    assert not scores[0].eligible
    assert scores[0].quality.is_rejected
    assert "trade sample size is insufficient" in scores[0].rejected_reasons
    assert "strategy metric quality is not trusted" in scores[0].rejected_reasons


def _snapshot(
    strategy_name: str,
    *,
    win_rate: Decimal = Decimal("0.60"),
    expectancy: Decimal = Decimal("0.01"),
    trade_count: int = 20,
    regime_label: str = "trend_up",
    quality: DataQualityStatus | None = None,
) -> StrategyMetricSnapshot:
    return StrategyMetricSnapshot(
        strategy_name=strategy_name,
        metrics=PerformanceMetrics(
            net_return=Decimal("0.20"),
            max_drawdown=Decimal("0.05"),
            profit_factor=Decimal("1.8"),
            sharpe_ratio=Decimal("1.2"),
            sortino_ratio=Decimal("1.5"),
            win_rate=win_rate,
            expectancy=expectancy,
            average_win=Decimal("0.03"),
            average_loss=Decimal("-0.01"),
            exposure_time_pct=Decimal("0.40"),
            tail_loss=Decimal("-0.02"),
            total_fees=Decimal("1"),
            trade_count=trade_count,
            costs_included=True,
            regime_performance=(
                RegimePerformance(
                    regime_label=regime_label,
                    period_count=10,
                    net_return=Decimal("0.12"),
                    max_drawdown=Decimal("0.03"),
                    win_rate=win_rate,
                    expectancy=expectancy,
                ),
            ),
        ),
        measured_at=NOW,
        quality=quality,
        source_refs={"metrics": f"fixture:{strategy_name}"},
    )
