from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.intelligence import (
    OnChainInput,
    OnChainPolicy,
    OnChainState,
    assess_onchain_intelligence,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_accumulation_assessment_is_explainable_and_actionable_context() -> None:
    assessment = assess_onchain_intelligence(_accumulation_input(), generated_at=NOW)

    assert assessment.state is OnChainState.ACCUMULATION
    assert assessment.accumulation_score == Decimal("0.7690")
    assert assessment.distribution_score == Decimal("0.2380")
    assert assessment.on_chain_score == Decimal("0.7480")
    assert assessment.confidence == Decimal("1.0000")
    assert assessment.actionable_context
    assert assessment.quality.is_trusted
    assert assessment.audit_payload()["state"] == "accumulation"
    assert len(assessment.evidence) == 15


def test_distribution_assessment_blocks_as_advisory_context() -> None:
    assessment = assess_onchain_intelligence(_distribution_input(), generated_at=NOW)

    assert assessment.state is OnChainState.DISTRIBUTION
    assert assessment.distribution_score == Decimal("0.8480")
    assert assessment.accumulation_score == Decimal("0.1940")
    assert assessment.actionable_context
    assert any("distribution_score" in reason for reason in assessment.reasons)


def test_network_stress_state_detects_weak_hash_rate_and_growth() -> None:
    assessment = assess_onchain_intelligence(_network_stress_input(), generated_at=NOW)

    assert assessment.state is OnChainState.NETWORK_STRESS
    assert assessment.on_chain_score < Decimal("0.50")
    assert assessment.confidence >= Decimal("0.45")


def test_stale_or_rejected_onchain_inputs_fail_closed() -> None:
    stale = assess_onchain_intelligence(_accumulation_input(stale=True), generated_at=NOW)
    rejected = assess_onchain_intelligence(
        _accumulation_input(quality=_rejected_quality()),
        generated_at=NOW,
    )

    assert stale.state is OnChainState.UNKNOWN
    assert stale.quality.is_rejected
    assert "on-chain inputs are stale" in stale.rejection_reasons
    assert rejected.state is OnChainState.UNKNOWN
    assert "on-chain input quality is rejected" in rejected.rejection_reasons


def test_degraded_onchain_quality_reduces_confidence_and_quality() -> None:
    assessment = assess_onchain_intelligence(
        _accumulation_input(quality=_degraded_quality()),
        generated_at=NOW,
    )

    assert assessment.state is OnChainState.ACCUMULATION
    assert assessment.quality.is_degraded
    assert not assessment.actionable_context
    assert assessment.confidence == Decimal("0.6300")


def test_low_confidence_policy_fails_closed() -> None:
    assessment = assess_onchain_intelligence(
        _network_stress_input(),
        generated_at=NOW,
        policy=OnChainPolicy(min_confidence=Decimal("0.95")),
    )

    assert assessment.state is OnChainState.UNKNOWN
    assert not assessment.actionable_context
    assert "on-chain confidence is below threshold" in assessment.rejection_reasons


def test_onchain_input_validates_score_bounds() -> None:
    with pytest.raises(ValueError, match="mvrv_score must be between 0 and 1"):
        _accumulation_input(mvrv_score=Decimal("1.10"))


def test_onchain_assessment_has_no_trading_authority() -> None:
    assessment = assess_onchain_intelligence(_accumulation_input(), generated_at=NOW)

    with pytest.raises(ValueError, match="cannot create signals"):
        assessment.create_signal()
    with pytest.raises(ValueError, match="cannot create order intents"):
        assessment.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        assessment.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        assessment.submit_order()


def test_public_imports_are_available() -> None:
    from abtp.intelligence import OnChainAssessment, OnChainEvidence

    assert OnChainAssessment is not None
    assert OnChainEvidence is not None


def _accumulation_input(
    *,
    mvrv_score: Decimal = Decimal("0.20"),
    quality: DataQualityStatus | None = None,
    stale: bool = False,
) -> OnChainInput:
    return OnChainInput(
        observed_at=NOW,
        mvrv_score=mvrv_score,
        sopr_score=Decimal("0.30"),
        nupl_score=Decimal("0.25"),
        exchange_inflow_score=Decimal("0.20"),
        exchange_outflow_score=Decimal("0.80"),
        whale_accumulation_score=Decimal("0.85"),
        miner_selling_score=Decimal("0.25"),
        dormancy_score=Decimal("0.30"),
        coin_days_destroyed_score=Decimal("0.30"),
        realized_price_position_score=Decimal("0.40"),
        hash_rate_score=Decimal("0.80"),
        network_growth_score=Decimal("0.75"),
        quality=quality or _trusted_quality(),
        source_refs={"mvrv": "fixture:mvrv"},
        stale=stale,
    )


def _distribution_input() -> OnChainInput:
    return OnChainInput(
        observed_at=NOW,
        mvrv_score=Decimal("0.90"),
        sopr_score=Decimal("0.85"),
        nupl_score=Decimal("0.85"),
        exchange_inflow_score=Decimal("0.90"),
        exchange_outflow_score=Decimal("0.20"),
        whale_accumulation_score=Decimal("0.20"),
        miner_selling_score=Decimal("0.85"),
        dormancy_score=Decimal("0.80"),
        coin_days_destroyed_score=Decimal("0.80"),
        realized_price_position_score=Decimal("0.85"),
        hash_rate_score=Decimal("0.70"),
        network_growth_score=Decimal("0.50"),
        quality=_trusted_quality(),
        source_refs={"exchange_inflow": "fixture:inflow"},
    )


def _network_stress_input() -> OnChainInput:
    return OnChainInput(
        observed_at=NOW,
        mvrv_score=Decimal("0.50"),
        sopr_score=Decimal("0.50"),
        nupl_score=Decimal("0.50"),
        exchange_inflow_score=Decimal("0.45"),
        exchange_outflow_score=Decimal("0.45"),
        whale_accumulation_score=Decimal("0.45"),
        miner_selling_score=Decimal("0.60"),
        dormancy_score=Decimal("0.50"),
        coin_days_destroyed_score=Decimal("0.50"),
        realized_price_position_score=Decimal("0.40"),
        hash_rate_score=Decimal("0.20"),
        network_growth_score=Decimal("0.25"),
        quality=_trusted_quality(),
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:trusted",
        checked_at=NOW,
    )


def _degraded_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.DEGRADED,
        issues=(
            DataQualityIssue(
                flag="fixture_degraded",
                severity=DataTrustLevel.DEGRADED,
                reason="fixture degraded",
            ),
        ),
        source_ref="fixture:degraded",
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
