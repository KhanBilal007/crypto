from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.intelligence import (
    CycleRiskLevel,
    MarketCycleInput,
    MarketCyclePhase,
    MarketCyclePolicy,
    assess_market_cycle,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_bull_expansion_cycle_is_advisory_and_explainable() -> None:
    assessment = assess_market_cycle(_cycle_input(), generated_at=NOW)

    assert assessment.phase is MarketCyclePhase.BULL_EXPANSION
    assert assessment.risk_level is CycleRiskLevel.LOW
    assert assessment.confidence == Decimal("0.5150")
    assert assessment.actionable_context
    assert assessment.suggested_allocation.allow_new_entries
    assert assessment.suggested_allocation.max_risk_asset_allocation == Decimal("0.70")
    assert assessment.audit_payload()["phase"] == "bull_expansion"
    assert len(assessment.evidence) == 8


def test_euphoria_and_capitulation_are_extreme_risk() -> None:
    euphoria = assess_market_cycle(
        _cycle_input(fear_greed_score=Decimal("0.90")),
        generated_at=NOW,
    )
    capitulation = assess_market_cycle(
        _cycle_input(
            btc_dominance_score=Decimal("0.20"),
            eth_dominance_score=Decimal("0.20"),
            altcoin_season_score=Decimal("0.10"),
            market_breadth_score=Decimal("0.10"),
            fear_greed_score=Decimal("0.10"),
            liquidity_score=Decimal("0.20"),
        ),
        generated_at=NOW,
    )

    assert euphoria.phase is MarketCyclePhase.BULL_EUPHORIA
    assert euphoria.risk_level is CycleRiskLevel.EXTREME
    assert not euphoria.suggested_allocation.allow_new_entries
    assert capitulation.phase is MarketCyclePhase.CAPITULATION
    assert capitulation.risk_level is CycleRiskLevel.EXTREME
    assert capitulation.suggested_allocation.min_cash_reserve == Decimal("0.80")


def test_distribution_bear_and_recovery_phases_are_detected() -> None:
    distribution = assess_market_cycle(
        _cycle_input(market_breadth_score=Decimal("0.30")),
        generated_at=NOW,
    )
    bear = assess_market_cycle(
        _cycle_input(
            btc_dominance_score=Decimal("0.20"),
            eth_dominance_score=Decimal("0.20"),
            altcoin_season_score=Decimal("0.20"),
            market_breadth_score=Decimal("0.30"),
            fear_greed_score=Decimal("0.30"),
            liquidity_score=Decimal("0.30"),
        ),
        generated_at=NOW,
    )
    recovery = assess_market_cycle(
        _cycle_input(
            btc_dominance_score=Decimal("0.45"),
            eth_dominance_score=Decimal("0.45"),
            altcoin_season_score=Decimal("0.45"),
            market_breadth_score=Decimal("0.50"),
            fear_greed_score=Decimal("0.50"),
            liquidity_score=Decimal("0.55"),
        ),
        generated_at=NOW,
    )

    assert distribution.phase is MarketCyclePhase.DISTRIBUTION
    assert distribution.risk_level is CycleRiskLevel.HIGH
    assert bear.phase is MarketCyclePhase.BEAR_MARKET
    assert recovery.phase is MarketCyclePhase.RECOVERY


def test_stale_or_rejected_cycle_inputs_fail_closed() -> None:
    stale = assess_market_cycle(_cycle_input(stale=True), generated_at=NOW)
    rejected = assess_market_cycle(_cycle_input(quality=_rejected_quality()), generated_at=NOW)

    assert stale.phase is MarketCyclePhase.UNKNOWN
    assert stale.quality.is_rejected
    assert "market-cycle inputs are stale" in stale.rejection_reasons
    assert rejected.phase is MarketCyclePhase.UNKNOWN
    assert "market-cycle input quality is rejected" in rejected.rejection_reasons


def test_low_confidence_policy_fails_closed() -> None:
    assessment = assess_market_cycle(
        _cycle_input(),
        generated_at=NOW,
        policy=MarketCyclePolicy(min_confidence=Decimal("0.90")),
    )

    assert assessment.phase is MarketCyclePhase.UNKNOWN
    assert not assessment.actionable_context
    assert "cycle confidence is below threshold" in assessment.rejection_reasons


def test_cycle_input_validates_score_bounds() -> None:
    with pytest.raises(ValueError, match="btc_dominance_score must be between 0 and 1"):
        _cycle_input(btc_dominance_score=Decimal("1.10"))


def test_market_cycle_assessment_has_no_trading_authority() -> None:
    assessment = assess_market_cycle(_cycle_input(), generated_at=NOW)

    with pytest.raises(ValueError, match="cannot create signals"):
        assessment.create_signal()
    with pytest.raises(ValueError, match="cannot create order intents"):
        assessment.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        assessment.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        assessment.submit_order()


def test_public_imports_are_available() -> None:
    from abtp.intelligence import CycleAllocationSuggestion, MarketCycleAssessment

    assert MarketCycleAssessment is not None
    assert CycleAllocationSuggestion is not None


def _cycle_input(
    *,
    btc_dominance_score: Decimal = Decimal("0.70"),
    eth_dominance_score: Decimal = Decimal("0.65"),
    altcoin_season_score: Decimal = Decimal("0.60"),
    market_breadth_score: Decimal = Decimal("0.75"),
    fear_greed_score: Decimal = Decimal("0.70"),
    liquidity_score: Decimal = Decimal("0.80"),
    quality: DataQualityStatus | None = None,
    stale: bool = False,
) -> MarketCycleInput:
    return MarketCycleInput(
        observed_at=NOW,
        btc_dominance_score=btc_dominance_score,
        eth_dominance_score=eth_dominance_score,
        altcoin_season_score=altcoin_season_score,
        market_breadth_score=market_breadth_score,
        fear_greed_score=fear_greed_score,
        liquidity_score=liquidity_score,
        quality=quality or _trusted_quality(),
        source_refs={"cycle": "fixture:cycle"},
        stale=stale,
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
                flag="fixture_rejected",
                severity=DataTrustLevel.REJECTED,
                reason="fixture rejected",
            ),
        ),
        source_ref="fixture:rejected",
        checked_at=NOW,
    )
