from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.intelligence import (
    FundamentalInput,
    FundamentalPolicy,
    FundamentalRating,
    FundamentalRiskGrade,
    assess_fundamental_asset,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_strong_fundamental_rating_is_explainable_and_actionable_context() -> None:
    assessment = assess_fundamental_asset(_strong_input(), generated_at=NOW)

    assert assessment.rating is FundamentalRating.STRONG
    assert assessment.long_term_score == Decimal("0.8182")
    assert assessment.risk_grade is FundamentalRiskGrade.LOW
    assert assessment.confidence == Decimal("0.8796")
    assert assessment.actionable_context
    assert assessment.quality.is_trusted
    assert assessment.audit_payload()["rating"] == "strong"
    assert len(assessment.evidence) == 16


def test_watchlist_rating_detects_mid_quality_project() -> None:
    assessment = assess_fundamental_asset(_mid_quality_input(), generated_at=NOW)

    assert assessment.rating is FundamentalRating.WATCHLIST
    assert assessment.long_term_score == Decimal("0.5147")
    assert assessment.risk_grade is FundamentalRiskGrade.HIGH
    assert assessment.actionable_context
    assert any("watchlist" in reason for reason in assessment.reasons)


def test_critical_security_or_liquidity_fails_closed() -> None:
    weak_security = assess_fundamental_asset(
        _strong_input(security_score=Decimal("0.20")),
        generated_at=NOW,
    )
    weak_liquidity = assess_fundamental_asset(
        _strong_input(liquidity_score=Decimal("0.20")),
        generated_at=NOW,
    )

    assert weak_security.rating is FundamentalRating.UNKNOWN
    assert weak_security.risk_grade is FundamentalRiskGrade.SEVERE
    assert not weak_security.actionable_context
    assert "security score is below critical floor" in weak_security.rejection_reasons
    assert weak_liquidity.rating is FundamentalRating.UNKNOWN
    assert "liquidity score is below critical floor" in weak_liquidity.rejection_reasons


def test_stale_or_rejected_fundamental_inputs_fail_closed() -> None:
    stale = assess_fundamental_asset(_strong_input(stale=True), generated_at=NOW)
    rejected = assess_fundamental_asset(
        _strong_input(quality=_rejected_quality()),
        generated_at=NOW,
    )

    assert stale.rating is FundamentalRating.UNKNOWN
    assert stale.quality.is_rejected
    assert "fundamental inputs are stale" in stale.rejection_reasons
    assert rejected.rating is FundamentalRating.UNKNOWN
    assert "fundamental input quality is rejected" in rejected.rejection_reasons


def test_degraded_fundamental_quality_reduces_confidence_and_quality() -> None:
    assessment = assess_fundamental_asset(
        _strong_input(quality=_degraded_quality()),
        generated_at=NOW,
    )

    assert assessment.rating is FundamentalRating.STRONG
    assert assessment.quality.is_degraded
    assert not assessment.actionable_context
    assert assessment.confidence == Decimal("0.6796")


def test_low_confidence_policy_fails_closed() -> None:
    assessment = assess_fundamental_asset(
        _mid_quality_input(),
        generated_at=NOW,
        policy=FundamentalPolicy(min_confidence=Decimal("0.95")),
    )

    assert assessment.rating is FundamentalRating.UNKNOWN
    assert assessment.risk_grade is FundamentalRiskGrade.SEVERE
    assert not assessment.actionable_context
    assert "fundamental confidence is below threshold" in assessment.rejection_reasons


def test_fundamental_input_validates_score_bounds() -> None:
    with pytest.raises(ValueError, match="market_cap_score must be between 0 and 1"):
        _strong_input(market_cap_score=Decimal("1.10"))


def test_fundamental_assessment_has_no_trading_authority() -> None:
    assessment = assess_fundamental_asset(_strong_input(), generated_at=NOW)

    with pytest.raises(ValueError, match="cannot create signals"):
        assessment.create_signal()
    with pytest.raises(ValueError, match="cannot create order intents"):
        assessment.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        assessment.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        assessment.submit_order()


def test_public_imports_are_available() -> None:
    from abtp.intelligence import FundamentalAssessment, FundamentalEvidence

    assert FundamentalAssessment is not None
    assert FundamentalEvidence is not None


def _strong_input(
    *,
    market_cap_score: Decimal = Decimal("0.90"),
    liquidity_score: Decimal = Decimal("0.85"),
    security_score: Decimal = Decimal("0.90"),
    quality: DataQualityStatus | None = None,
    stale: bool = False,
) -> FundamentalInput:
    return FundamentalInput(
        observed_at=NOW,
        asset_symbol="btc",
        market_cap_score=market_cap_score,
        liquidity_score=liquidity_score,
        developer_activity_score=Decimal("0.80"),
        github_score=Decimal("0.78"),
        tvl_score=Decimal("0.75"),
        staking_score=Decimal("0.70"),
        tokenomics_score=Decimal("0.86"),
        inflation_control_score=Decimal("0.82"),
        partnerships_score=Decimal("0.72"),
        institutional_adoption_score=Decimal("0.76"),
        security_score=security_score,
        roadmap_score=Decimal("0.78"),
        community_score=Decimal("0.74"),
        governance_score=Decimal("0.70"),
        quality=quality or _trusted_quality(),
        stale=stale,
        source_refs={"market_cap_score": "fixture:fundamentals:market-cap"},
    )


def _mid_quality_input() -> FundamentalInput:
    return FundamentalInput(
        observed_at=NOW,
        asset_symbol="ETH",
        market_cap_score=Decimal("0.55"),
        liquidity_score=Decimal("0.55"),
        developer_activity_score=Decimal("0.58"),
        github_score=Decimal("0.52"),
        tvl_score=Decimal("0.50"),
        staking_score=Decimal("0.48"),
        tokenomics_score=Decimal("0.48"),
        inflation_control_score=Decimal("0.50"),
        partnerships_score=Decimal("0.45"),
        institutional_adoption_score=Decimal("0.50"),
        security_score=Decimal("0.55"),
        roadmap_score=Decimal("0.50"),
        community_score=Decimal("0.48"),
        governance_score=Decimal("0.45"),
        quality=_trusted_quality(),
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:fundamentals",
        checked_at=NOW,
    )


def _degraded_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.DEGRADED,
        issues=(
            DataQualityIssue(
                flag="partial_provider_coverage",
                severity=DataTrustLevel.DEGRADED,
                reason="some optional fundamental sources are unavailable",
            ),
        ),
        source_ref="fixture:fundamentals:degraded",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="malformed_fundamental_payload",
                severity=DataTrustLevel.REJECTED,
                reason="fundamental payload cannot be trusted",
            ),
        ),
        source_ref="fixture:fundamentals:rejected",
        checked_at=NOW,
    )
