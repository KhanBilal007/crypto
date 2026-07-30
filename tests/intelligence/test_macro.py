from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.intelligence import (
    MacroInput,
    MacroNarrativeMode,
    MacroNarrativePolicy,
    NarrativeObservation,
    NarrativeTheme,
    assess_macro_narrative,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_risk_on_macro_narrative_assessment_is_explainable() -> None:
    assessment = assess_macro_narrative(
        _risk_on_macro(),
        _strong_narratives(),
        generated_at=NOW,
    )

    assert assessment.mode is MacroNarrativeMode.RISK_ON
    assert assessment.leading_narrative is NarrativeTheme.AI
    assert assessment.macro_risk_score == Decimal("0.3008")
    assert assessment.narrative_strength == Decimal("0.8330")
    assert assessment.risk_on_score == Decimal("0.7456")
    assert assessment.confidence == Decimal("0.9275")
    assert assessment.actionable_context
    assert assessment.quality.is_trusted
    assert assessment.audit_payload()["mode"] == "risk_on"
    assert len(assessment.evidence) == 19


def test_elevated_macro_risk_fails_closed() -> None:
    assessment = assess_macro_narrative(
        _risk_off_macro(),
        _strong_narratives(),
        generated_at=NOW,
    )

    assert assessment.mode is MacroNarrativeMode.UNKNOWN
    assert assessment.macro_risk_score >= Decimal("0.65")
    assert not assessment.actionable_context
    assert assessment.quality.is_rejected
    assert "macro risk score is elevated" in assessment.rejection_reasons


def test_insufficient_narratives_fail_closed() -> None:
    assessment = assess_macro_narrative(
        _risk_on_macro(),
        _strong_narratives()[:2],
        generated_at=NOW,
    )

    assert assessment.mode is MacroNarrativeMode.UNKNOWN
    assert "not enough narrative themes supplied" in assessment.rejection_reasons
    assert assessment.quality.is_rejected


def test_stale_or_rejected_macro_narrative_inputs_fail_closed() -> None:
    stale_macro = assess_macro_narrative(
        _risk_on_macro(stale=True),
        _strong_narratives(),
        generated_at=NOW,
    )
    rejected_narrative = assess_macro_narrative(
        _risk_on_macro(),
        _strong_narratives(quality_theme=NarrativeTheme.DEFI, quality=_rejected_quality()),
        generated_at=NOW,
    )

    assert stale_macro.mode is MacroNarrativeMode.UNKNOWN
    assert "macro inputs are stale" in stale_macro.rejection_reasons
    assert rejected_narrative.mode is MacroNarrativeMode.UNKNOWN
    assert "defi narrative quality is rejected" in rejected_narrative.rejection_reasons


def test_degraded_macro_narrative_quality_reduces_confidence_and_quality() -> None:
    assessment = assess_macro_narrative(
        _risk_on_macro(),
        _strong_narratives(quality_theme=NarrativeTheme.LAYER2, quality=_degraded_quality()),
        generated_at=NOW,
    )

    assert assessment.mode is MacroNarrativeMode.RISK_ON
    assert assessment.quality.is_degraded
    assert not assessment.actionable_context
    assert assessment.confidence == Decimal("0.7775")


def test_low_confidence_policy_fails_closed() -> None:
    assessment = assess_macro_narrative(
        _risk_on_macro(),
        _strong_narratives(),
        generated_at=NOW,
        policy=MacroNarrativePolicy(min_confidence=Decimal("0.95")),
    )

    assert assessment.mode is MacroNarrativeMode.UNKNOWN
    assert not assessment.actionable_context
    assert "macro narrative confidence is below threshold" in assessment.rejection_reasons


def test_macro_input_validates_score_bounds() -> None:
    with pytest.raises(ValueError, match="interest_rate_pressure_score must be between 0 and 1"):
        _risk_on_macro(interest_rate_pressure_score=Decimal("1.10"))


def test_macro_narrative_assessment_has_no_trading_authority() -> None:
    assessment = assess_macro_narrative(
        _risk_on_macro(),
        _strong_narratives(),
        generated_at=NOW,
    )

    with pytest.raises(ValueError, match="cannot create signals"):
        assessment.create_signal()
    with pytest.raises(ValueError, match="cannot create order intents"):
        assessment.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        assessment.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        assessment.submit_order()


def test_public_imports_are_available() -> None:
    from abtp.intelligence import MacroNarrativeAssessment, MacroNarrativeEvidence

    assert MacroNarrativeAssessment is not None
    assert MacroNarrativeEvidence is not None


def _risk_on_macro(
    *,
    interest_rate_pressure_score: Decimal = Decimal("0.25"),
    quality: DataQualityStatus | None = None,
    stale: bool = False,
) -> MacroInput:
    return MacroInput(
        observed_at=NOW,
        interest_rate_pressure_score=interest_rate_pressure_score,
        fed_hawkishness_score=Decimal("0.30"),
        ecb_hawkishness_score=Decimal("0.28"),
        inflation_pressure_score=Decimal("0.32"),
        cpi_surprise_score=Decimal("0.35"),
        ppi_surprise_score=Decimal("0.30"),
        dollar_strength_score=Decimal("0.35"),
        bond_yield_pressure_score=Decimal("0.33"),
        gold_safety_bid_score=Decimal("0.30"),
        oil_inflation_pressure_score=Decimal("0.30"),
        nasdaq_strength_score=Decimal("0.76"),
        sp500_strength_score=Decimal("0.72"),
        etf_flow_score=Decimal("0.78"),
        quality=quality or _trusted_quality(),
        stale=stale,
        source_refs={"etf_flow_score": "fixture:macro:etf-flows"},
    )


def _risk_off_macro() -> MacroInput:
    return MacroInput(
        observed_at=NOW,
        interest_rate_pressure_score=Decimal("0.82"),
        fed_hawkishness_score=Decimal("0.86"),
        ecb_hawkishness_score=Decimal("0.78"),
        inflation_pressure_score=Decimal("0.85"),
        cpi_surprise_score=Decimal("0.78"),
        ppi_surprise_score=Decimal("0.72"),
        dollar_strength_score=Decimal("0.82"),
        bond_yield_pressure_score=Decimal("0.84"),
        gold_safety_bid_score=Decimal("0.75"),
        oil_inflation_pressure_score=Decimal("0.76"),
        nasdaq_strength_score=Decimal("0.25"),
        sp500_strength_score=Decimal("0.28"),
        etf_flow_score=Decimal("0.22"),
        quality=_trusted_quality(),
    )


def _strong_narratives(
    *,
    quality_theme: NarrativeTheme | None = None,
    quality: DataQualityStatus | None = None,
) -> tuple[NarrativeObservation, ...]:
    return (
        _narrative(
            NarrativeTheme.AI,
            Decimal("0.86"),
            Decimal("0.84"),
            Decimal("0.78"),
            Decimal("0.82"),
            quality_theme,
            quality,
        ),
        _narrative(
            NarrativeTheme.RWA,
            Decimal("0.72"),
            Decimal("0.70"),
            Decimal("0.64"),
            Decimal("0.68"),
            quality_theme,
            quality,
        ),
        _narrative(
            NarrativeTheme.LAYER2,
            Decimal("0.68"),
            Decimal("0.65"),
            Decimal("0.70"),
            Decimal("0.62"),
            quality_theme,
            quality,
        ),
        _narrative(
            NarrativeTheme.DEFI,
            Decimal("0.62"),
            Decimal("0.60"),
            Decimal("0.66"),
            Decimal("0.58"),
            quality_theme,
            quality,
        ),
        _narrative(
            NarrativeTheme.GAMING,
            Decimal("0.50"),
            Decimal("0.52"),
            Decimal("0.48"),
            Decimal("0.55"),
            quality_theme,
            quality,
        ),
    )


def _narrative(
    theme: NarrativeTheme,
    strength: Decimal,
    momentum: Decimal,
    liquidity: Decimal,
    attention: Decimal,
    quality_theme: NarrativeTheme | None = None,
    quality: DataQualityStatus | None = None,
) -> NarrativeObservation:
    return NarrativeObservation(
        theme=theme,
        strength_score=strength,
        momentum_score=momentum,
        liquidity_score=liquidity,
        attention_score=attention,
        quality=quality if theme is quality_theme else _trusted_quality(),
        observed_at=NOW,
        source_ref=f"fixture:macro:narrative:{theme.value}",
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:macro",
        checked_at=NOW,
    )


def _degraded_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.DEGRADED,
        issues=(
            DataQualityIssue(
                flag="partial_macro_narrative_coverage",
                severity=DataTrustLevel.DEGRADED,
                reason="some optional macro narrative sources are unavailable",
            ),
        ),
        source_ref="fixture:macro:degraded",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="malformed_macro_narrative_payload",
                severity=DataTrustLevel.REJECTED,
                reason="macro narrative payload cannot be trusted",
            ),
        ),
        source_ref="fixture:macro:rejected",
        checked_at=NOW,
    )
