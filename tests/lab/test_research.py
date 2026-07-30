from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.ai import (
    ModelApprovalStatus,
    ModelComparisonResult,
    ModelLifecycleStatus,
)
from abtp.backtesting import PerformanceMetrics, RegimePerformance
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.lab import (
    ParameterCandidate,
    PromotionRecommendation,
    ResearchExperimentSpec,
    ResearchExperimentType,
    StrategyBenchmarkInput,
    StrategyCatalogueEntry,
    StrategyCatalogueStatus,
    build_research_report,
    compare_strategies,
)
from abtp.validation import RobustnessScore

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_model_research_report_recommends_candidate_for_review() -> None:
    report = build_research_report(
        ResearchExperimentSpec(
            experiment_id="exp-model-001",
            experiment_type=ResearchExperimentType.MODEL_COMPARISON,
            title="baseline model comparison",
            baseline_ref="baseline:v1",
            candidate_refs=("baseline:v2",),
            hypothesis="candidate improves validation quality",
            evaluation_window="2026-01 validation",
            created_at=NOW,
            source_refs={"plan": "fixture:stage-069"},
        ),
        model_results=(
            _model_result("baseline:v1", score=Decimal("0.62"), rank=2),
            _model_result("baseline:v2", score=Decimal("0.74"), rank=1),
        ),
        generated_at=NOW,
    )

    assert report.promotion_advice.recommendation is PromotionRecommendation.PROMOTE_TO_REVIEW
    assert report.recommended_candidate_ref == "baseline:v2"
    assert report.quality.is_trusted
    assert report.audit_payload()["experiment_type"] == "model_comparison"


def test_strategy_research_report_uses_existing_benchmark_evidence() -> None:
    benchmark = compare_strategies(
        (
            _strategy_input(
                "production-v1",
                status=StrategyCatalogueStatus.BENCHMARK,
                net_return=Decimal("-0.05"),
            ),
            _strategy_input("trend-v2", net_return=Decimal("0.30")),
        ),
        baseline_key="production-v1",
        regime_label="trend_up",
        generated_at=NOW,
    )

    report = build_research_report(
        ResearchExperimentSpec(
            experiment_id="exp-strategy-001",
            experiment_type=ResearchExperimentType.REGIME_EVALUATION,
            title="trend regime research",
            baseline_ref="production-v1",
            candidate_refs=("trend-v2",),
            hypothesis="trend candidate improves trend-up results",
            evaluation_window="walk-forward fixture",
            regime_label="trend_up",
            created_at=NOW,
        ),
        strategy_results=benchmark.results,
        generated_at=NOW,
    )

    assert report.recommended_candidate_ref == "trend-v2"
    assert report.results[0].result_type is ResearchExperimentType.REGIME_EVALUATION
    assert any("regime_score=" in item for item in report.results[0].evidence)


def test_hyperparameter_experiment_preserves_candidate_metadata() -> None:
    candidate = ParameterCandidate(
        strategy_key="trend-v2",
        values={"lookback": Decimal("12")},
        candidate_ref="trend-v2:candidate:001",
        source_ref="fixture:parameter_space",
    )

    spec = ResearchExperimentSpec(
        experiment_id="exp-param-001",
        experiment_type=ResearchExperimentType.HYPERPARAMETER_TEST,
        title="lookback parameter test",
        baseline_ref="production-v1",
        candidate_refs=("trend-v2",),
        hypothesis="shorter lookback improves out-of-sample behavior",
        evaluation_window="walk-forward fixture",
        parameter_candidates=(candidate,),
        created_at=NOW,
    )

    assert spec.as_dict()["parameter_candidates"] == [candidate.as_dict()]


def test_missing_candidate_result_keeps_experiment_research_only() -> None:
    report = build_research_report(
        ResearchExperimentSpec(
            experiment_id="exp-missing-001",
            experiment_type=ResearchExperimentType.MODEL_COMPARISON,
            title="missing candidate",
            baseline_ref="baseline:v1",
            candidate_refs=("baseline:v2",),
            hypothesis="candidate should be present",
            evaluation_window="validation fixture",
            created_at=NOW,
        ),
        model_results=(_model_result("baseline:v1", score=Decimal("0.62"), rank=1),),
        generated_at=NOW,
    )

    assert report.promotion_advice.recommendation is PromotionRecommendation.KEEP_RESEARCH_ONLY
    assert "missing results for candidates: baseline:v2" in report.rejected_reasons
    assert report.quality.is_degraded


def test_rejected_candidate_quality_fails_closed() -> None:
    rejected_quality = DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_research_fixture",
                severity=DataTrustLevel.REJECTED,
                reason="candidate data is rejected",
            ),
        ),
        source_ref="fixture:quality",
        checked_at=NOW,
    )
    report = build_research_report(
        ResearchExperimentSpec(
            experiment_id="exp-quality-001",
            experiment_type=ResearchExperimentType.MODEL_COMPARISON,
            title="quality gate",
            baseline_ref="baseline:v1",
            candidate_refs=("baseline:v2",),
            hypothesis="quality must stay trusted",
            evaluation_window="validation fixture",
            created_at=NOW,
        ),
        model_results=(
            _model_result("baseline:v1", score=Decimal("0.62"), rank=2),
            _model_result("baseline:v2", score=Decimal("0.80"), rank=1, quality=rejected_quality),
        ),
        generated_at=NOW,
    )

    assert report.promotion_advice.recommendation is PromotionRecommendation.REJECT
    assert report.results[0].quality.is_rejected
    assert "candidate quality is not trusted" in report.results[0].rejected_reasons


def test_research_report_has_no_prediction_signal_risk_or_order_authority() -> None:
    report = build_research_report(
        ResearchExperimentSpec(
            experiment_id="exp-safe-001",
            experiment_type=ResearchExperimentType.MODEL_COMPARISON,
            title="authority boundary",
            baseline_ref="baseline:v1",
            candidate_refs=("baseline:v2",),
            hypothesis="research cannot execute",
            evaluation_window="validation fixture",
            created_at=NOW,
        ),
        model_results=(
            _model_result("baseline:v1", score=Decimal("0.62"), rank=2),
            _model_result("baseline:v2", score=Decimal("0.74"), rank=1),
        ),
        generated_at=NOW,
    )

    with pytest.raises(ValueError, match="cannot serve predictions"):
        report.predict(object())
    with pytest.raises(ValueError, match="cannot create strategy signals"):
        report.create_signal(object())
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk(object())
    with pytest.raises(ValueError, match="cannot create order intents"):
        report.create_order_intent(object())
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order(object())


def test_public_imports_are_available() -> None:
    import abtp.lab as lab

    assert lab.build_research_report is build_research_report
    assert lab.ResearchExperimentType is ResearchExperimentType


def _model_result(
    model_ref: str,
    *,
    score: Decimal,
    rank: int,
    quality: DataQualityStatus | None = None,
) -> ModelComparisonResult:
    return ModelComparisonResult(
        model_ref=model_ref,
        score=score,
        eligible=quality is None or quality.is_trusted,
        rank=rank,
        rejected_reasons=(),
        evidence=(f"model_ref={model_ref}", f"score={score}"),
        quality=quality or _trusted_quality(model_ref),
        approval_status=ModelApprovalStatus.PAPER_APPROVED,
        lifecycle_status=ModelLifecycleStatus.CANDIDATE,
        source_refs={"model": f"fixture:{model_ref}"},
    )


def _strategy_input(
    key: str,
    *,
    status: StrategyCatalogueStatus = StrategyCatalogueStatus.CANDIDATE,
    net_return: Decimal,
) -> StrategyBenchmarkInput:
    return StrategyBenchmarkInput(
        entry=StrategyCatalogueEntry(
            key=key,
            name=key,
            version="1.0",
            family="trend",
            status=status,
            regime_suitability=("trend_up",),
            created_at=NOW,
            source_refs={"strategy": f"fixture:{key}"},
        ),
        metrics=_metrics(net_return),
        measured_at=NOW,
        robustness=_robustness(key),
        source_refs={"metrics": f"fixture:metrics:{key}"},
    )


def _metrics(net_return: Decimal) -> PerformanceMetrics:
    return PerformanceMetrics(
        net_return=net_return,
        max_drawdown=Decimal("0.04"),
        profit_factor=Decimal("1.9"),
        sharpe_ratio=Decimal("1.2"),
        sortino_ratio=Decimal("1.4"),
        win_rate=Decimal("0.64"),
        expectancy=net_return / Decimal("10"),
        average_win=Decimal("0.03"),
        average_loss=Decimal("-0.01"),
        exposure_time_pct=Decimal("0.40"),
        tail_loss=Decimal("-0.02"),
        total_fees=Decimal("1"),
        trade_count=24,
        costs_included=True,
        regime_performance=(
            RegimePerformance(
                regime_label="trend_up",
                period_count=12,
                net_return=net_return,
                max_drawdown=Decimal("0.03"),
                win_rate=Decimal("0.70"),
                expectancy=Decimal("0.02"),
            ),
        ),
    )


def _robustness(strategy_name: str) -> RobustnessScore:
    quality = DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref=f"fixture:robustness:{strategy_name}",
        checked_at=NOW,
    )
    return RobustnessScore(
        strategy_name=strategy_name,
        total_score=Decimal("0.82"),
        pass_ratio=Decimal("0.90"),
        average_out_of_sample_return=Decimal("0.05"),
        worst_out_of_sample_drawdown=Decimal("0.04"),
        average_train_test_return_gap=Decimal("0.02"),
        parameter_stability_score=Decimal("0.90"),
        regime_coverage={"trend_up": 12},
        accepted_for_promotion=True,
        rejected_reasons=(),
        evidence=(f"strategy_name={strategy_name}", "fixture robustness"),
        quality=quality,
        policy_version="stage-039.v1",
        generated_at=NOW,
    )


def _trusted_quality(source_ref: str) -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref=f"fixture:{source_ref}",
        checked_at=NOW,
    )
