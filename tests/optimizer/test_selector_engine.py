from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from sqlite3 import Connection
from uuid import UUID

import pytest

from abtp.audit import DecisionAuditRecorder, build_audit_event
from abtp.backtesting import PerformanceMetrics, RegimePerformance
from abtp.config import TradingMode
from abtp.optimizer import (
    StrategyMetricSnapshot,
    StrategyOptimisationRequest,
    StrategyOptimiserEngine,
    StrategySelectionPolicy,
    optimiser_confidence_adjustment,
)
from abtp.repositories import AuditRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)
CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000038")


def test_optimiser_selects_best_strategy_and_builds_explainable_report() -> None:
    engine = StrategyOptimiserEngine()
    report = engine.optimise(
        StrategyOptimisationRequest(
            candidates=(
                _snapshot("trend-v1", win_rate=Decimal("0.72"), expectancy=Decimal("0.02")),
                _snapshot("range-v1", win_rate=Decimal("0.55"), expectancy=Decimal("0.005")),
            ),
            regime_label="trend_up",
            generated_at=NOW,
            source_refs={"regime": "fixture:trend_up"},
        )
    )

    assert report.recommendation.selected_strategy == "trend-v1"
    assert report.recommendation.recommended
    assert "selected trend-v1" in report.recommendation.explanation
    assert optimiser_confidence_adjustment(report) > Decimal("0")
    assert report.audit_payload()["selected_strategy"] == "trend-v1"


def test_live_strategy_change_requires_manual_approval() -> None:
    engine = StrategyOptimiserEngine()
    report = engine.optimise(
        StrategyOptimisationRequest(
            candidates=(_snapshot("trend-v1"),),
            regime_label="trend_up",
            mode=TradingMode.LIVE,
            generated_at=NOW,
            manual_approval_for_live_change=False,
        )
    )

    assert report.recommendation.selected_strategy is None
    assert report.recommendation.manual_approval_required
    assert "manual approval required before live strategy change" in (
        report.recommendation.rejected_reasons
    )
    with pytest.raises(ValueError, match="manual approval"):
        report.recommendation.require_recommended()


def test_underperforming_disable_can_auto_apply_only_in_paper_or_research() -> None:
    engine = StrategyOptimiserEngine(
        selection_policy=StrategySelectionPolicy(underperforming_score=Decimal("0.80"))
    )
    paper_report = engine.optimise(
        StrategyOptimisationRequest(
            candidates=(
                _snapshot("weak-v1", win_rate=Decimal("0.40"), expectancy=Decimal("-0.01")),
            ),
            regime_label="trend_up",
            mode=TradingMode.PAPER,
            generated_at=NOW,
        )
    )
    live_report = engine.optimise(
        StrategyOptimisationRequest(
            candidates=(
                _snapshot("weak-v1", win_rate=Decimal("0.40"), expectancy=Decimal("-0.01")),
            ),
            regime_label="trend_up",
            mode=TradingMode.LIVE,
            generated_at=NOW,
            manual_approval_for_live_change=True,
        )
    )

    assert paper_report.recommendation.disable_recommendations == ("weak-v1",)
    assert paper_report.recommendation.can_auto_apply_disable
    assert live_report.recommendation.disable_recommendations == ("weak-v1",)
    assert not live_report.recommendation.can_auto_apply_disable


def test_optimiser_report_audit_payload_can_be_recorded(migrated_connection: Connection) -> None:
    report = StrategyOptimiserEngine().optimise(
        StrategyOptimisationRequest(
            candidates=(_snapshot("trend-v1"),),
            regime_label="trend_up",
            generated_at=NOW,
            risk_limits_ref="config:risk:fixture",
        )
    )
    recorder = DecisionAuditRecorder(AuditRepository(migrated_connection))

    recorder.append(
        build_audit_event(
            event_type="strategy_optimisation",
            occurred_at=NOW,
            payload=report.audit_payload(),
            correlation_id=CORRELATION_ID,
        )
    )
    trail = recorder.reconstruct(str(CORRELATION_ID))

    assert trail.events[0].payload["selected_strategy"] == "trend-v1"
    assert trail.events[0].payload["risk_limits_ref"] == "config:risk:fixture"


def test_optimiser_has_no_signal_or_order_authority() -> None:
    engine = StrategyOptimiserEngine()

    with pytest.raises(ValueError, match="cannot submit orders"):
        engine.submit_order(object())
    with pytest.raises(ValueError, match="cannot create strategy signals"):
        engine.create_signal(object())


def test_public_imports_are_available() -> None:
    import abtp.optimizer as optimizer

    assert optimizer.StrategyOptimiserEngine is StrategyOptimiserEngine


def _snapshot(
    strategy_name: str,
    *,
    win_rate: Decimal = Decimal("0.70"),
    expectancy: Decimal = Decimal("0.02"),
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
            trade_count=20,
            costs_included=True,
            regime_performance=(
                RegimePerformance(
                    regime_label="trend_up",
                    period_count=10,
                    net_return=Decimal("0.12"),
                    max_drawdown=Decimal("0.03"),
                    win_rate=win_rate,
                    expectancy=expectancy,
                ),
            ),
        ),
        measured_at=NOW,
        source_refs={"metrics": f"fixture:{strategy_name}"},
    )
