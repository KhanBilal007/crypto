from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.risk import (
    InstitutionalStressInput,
    InstitutionalStressPolicy,
    InstitutionalStressReport,
    StressRecommendationType,
    StressRiskRecommendation,
    StressScenarioDefinition,
    StressScenarioType,
    default_stress_scenarios,
    run_institutional_stress_test,
)

NOW = datetime(2026, 2, 1, tzinfo=UTC)


def test_institutional_stress_safe_custom_scenarios_are_accepted_for_review() -> None:
    report = run_institutional_stress_test(
        _stress_input(
            risk_asset=Decimal("0.40"), stablecoin=Decimal("0.20"), exchange=Decimal("0.10")
        ),
        scenarios=_mild_scenarios(),
        policy=InstitutionalStressPolicy(
            min_survival_score=Decimal("1"),
            max_worst_drawdown=Decimal("0.20"),
            max_recovery_days=60,
        ),
        generated_at=NOW,
    )

    assert isinstance(report, InstitutionalStressReport)
    assert report.advisory_only is True
    assert report.acceptable_for_risk_review
    assert report.portfolio_survival_score == Decimal("1.0000")
    assert report.worst_case_drawdown == Decimal("0.1280")
    assert report.recovery_time_estimate_days == 23
    assert (
        report.recommendations[0].recommendation_type is StressRecommendationType.ACCEPT_FOR_REVIEW
    )
    assert report.audit_payload()["scenario_count"] == 3


def test_default_institutional_stress_detects_crash_and_liquidity_failure() -> None:
    report = run_institutional_stress_test(
        _stress_input(
            risk_asset=Decimal("0.70"), stablecoin=Decimal("0.10"), exchange=Decimal("0.20")
        ),
        generated_at=NOW,
    )

    assert not report.acceptable_for_risk_review
    assert report.quality.is_rejected
    assert report.portfolio_survival_score < Decimal("1")
    assert report.worst_case_drawdown == Decimal("0.5180")
    assert any("worst-case drawdown" in reason for reason in report.rejection_reasons)
    assert any("survival score" in reason for reason in report.rejection_reasons)
    assert {recommendation.recommendation_type for recommendation in report.recommendations} == {
        StressRecommendationType.PAUSE_NEW_ENTRIES,
        StressRecommendationType.MANUAL_REVIEW,
        StressRecommendationType.INCREASE_CASH,
    }


def test_recovery_time_limit_fails_closed() -> None:
    report = run_institutional_stress_test(
        _stress_input(risk_asset=Decimal("0.20")),
        scenarios=(
            StressScenarioDefinition(
                scenario_type=StressScenarioType.REGULATORY_SHOCK,
                severity_pct=Decimal("0.10"),
                risk_asset_loss_multiplier=Decimal("1"),
                recovery_days=200,
                blocks_trading=True,
                source_ref="fixture:long_recovery",
            ),
        ),
        policy=InstitutionalStressPolicy(
            min_survival_score=Decimal("1"),
            max_worst_drawdown=Decimal("0.25"),
            max_recovery_days=90,
        ),
        generated_at=NOW,
    )

    assert report.quality.is_rejected
    assert report.recovery_time_estimate_days == 204
    assert any("recovery estimate" in reason for reason in report.rejection_reasons)


def test_rejected_or_stale_stress_input_fails_closed() -> None:
    report = run_institutional_stress_test(
        _stress_input(quality=_rejected_quality(), stale=True),
        scenarios=_mild_scenarios(),
        generated_at=NOW,
    )

    assert report.quality.is_rejected
    assert "stress input quality is rejected" in report.rejection_reasons
    assert "stress input is stale" in report.rejection_reasons
    assert "institutional_stress_rejection" in report.quality.flags


def test_stress_report_has_no_signal_risk_or_order_authority() -> None:
    report = run_institutional_stress_test(
        _stress_input(risk_asset=Decimal("0.20")),
        scenarios=_mild_scenarios(),
        generated_at=NOW,
    )

    with pytest.raises(ValueError, match="cannot create signals"):
        report.create_signal()
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk()
    with pytest.raises(ValueError, match="cannot create order intents"):
        report.create_order_intent()
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()


def test_stress_recommendations_cannot_execute_automatically() -> None:
    with pytest.raises(ValueError, match="cannot execute automatically"):
        StressRiskRecommendation(
            recommendation_type=StressRecommendationType.REDUCE_ALLOCATION,
            rationale="fixture unsafe recommendation",
            severity=DataTrustLevel.DEGRADED,
            evidence_refs=("fixture:stress",),
            can_execute_automatically=True,
        )


def test_stress_public_imports_and_default_scenarios() -> None:
    scenarios = default_stress_scenarios()

    assert InstitutionalStressReport.__name__ == "InstitutionalStressReport"
    assert {scenario.scenario_type for scenario in scenarios} == {
        StressScenarioType.MARKET_CRASH,
        StressScenarioType.STABLECOIN_DEPEG,
        StressScenarioType.EXCHANGE_INSOLVENCY,
        StressScenarioType.FLASH_CRASH,
        StressScenarioType.LIQUIDITY_EVAPORATION,
        StressScenarioType.REGULATORY_SHOCK,
        StressScenarioType.NETWORK_OUTAGE,
    }


def _stress_input(
    *,
    risk_asset: Decimal = Decimal("0.30"),
    stablecoin: Decimal = Decimal("0.20"),
    exchange: Decimal = Decimal("0.10"),
    quality: DataQualityStatus | None = None,
    stale: bool = False,
) -> InstitutionalStressInput:
    return InstitutionalStressInput(
        starting_equity=Decimal("1000"),
        cash_pct=DECIMAL_ONE - risk_asset - stablecoin,
        risk_asset_exposure_pct=risk_asset,
        stablecoin_exposure_pct=stablecoin,
        exchange_exposure_pct=exchange,
        quality=quality or _trusted_quality(),
        observed_at=NOW,
        source_refs={"portfolio": "fixture:portfolio"},
        stale=stale,
    )


def _mild_scenarios() -> tuple[StressScenarioDefinition, ...]:
    return (
        StressScenarioDefinition(
            scenario_type=StressScenarioType.MARKET_CRASH,
            severity_pct=Decimal("0.30"),
            risk_asset_loss_multiplier=Decimal("1"),
            liquidity_haircut_pct=Decimal("0.02"),
            recovery_days=20,
            source_ref="fixture:market_crash_30",
        ),
        StressScenarioDefinition(
            scenario_type=StressScenarioType.STABLECOIN_DEPEG,
            severity_pct=Decimal("0.10"),
            risk_asset_loss_multiplier=Decimal("0"),
            stablecoin_loss_multiplier=Decimal("1"),
            recovery_days=14,
            source_ref="fixture:depeg_10",
        ),
        StressScenarioDefinition(
            scenario_type=StressScenarioType.NETWORK_OUTAGE,
            severity_pct=Decimal("0.08"),
            risk_asset_loss_multiplier=Decimal("0.25"),
            exchange_loss_multiplier=Decimal("0.25"),
            recovery_days=7,
            blocks_trading=True,
            source_ref="fixture:network_outage",
        ),
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:trusted",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_stress_input",
                severity=DataTrustLevel.REJECTED,
                reason="fixture rejected stress input",
            ),
        ),
        source_ref="fixture:rejected",
        checked_at=NOW,
    )


DECIMAL_ONE = Decimal("1")
