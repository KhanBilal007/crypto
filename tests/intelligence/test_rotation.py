from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.intelligence import (
    CapitalBucket,
    CapitalFlowObservation,
    CapitalRotationPolicy,
    RotationMode,
    assess_capital_rotation,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_sector_rotation_assessment_is_explainable_and_actionable_context() -> None:
    assessment = assess_capital_rotation(_sector_rotation_observations(), generated_at=NOW)

    assert assessment.mode is RotationMode.SECTOR_ROTATION
    assert assessment.leading_bucket is CapitalBucket.AI
    assert assessment.lagging_bucket is CapitalBucket.STABLECOINS
    assert assessment.capital_flow_map["ai"] == "strong_inflow"
    assert assessment.capital_flow_map["stablecoins"] == "moderate_outflow"
    assert assessment.rotation_probability == Decimal("0.3977")
    assert assessment.risk_off_score == Decimal("0.3155")
    assert assessment.confidence == Decimal("0.8117")
    assert assessment.actionable_context
    assert assessment.quality.is_trusted
    assert assessment.audit_payload()["leading_bucket"] == "ai"
    assert len(assessment.evidence) == 9


def test_risk_off_stablecoin_rotation_fails_closed() -> None:
    assessment = assess_capital_rotation(_risk_off_observations(), generated_at=NOW)

    assert assessment.mode is RotationMode.UNKNOWN
    assert assessment.leading_bucket is CapitalBucket.STABLECOINS
    assert assessment.risk_off_score >= Decimal("0.62")
    assert not assessment.actionable_context
    assert assessment.quality.is_rejected
    assert "risk-off capital flow is elevated" in assessment.rejection_reasons


def test_missing_required_bucket_fails_closed() -> None:
    observations = tuple(
        item for item in _sector_rotation_observations() if item.bucket is not CapitalBucket.ETH
    )
    assessment = assess_capital_rotation(observations, generated_at=NOW)

    assert assessment.mode is RotationMode.UNKNOWN
    assert "required bucket eth is missing" in assessment.rejection_reasons
    assert assessment.quality.is_rejected


def test_stale_or_rejected_rotation_inputs_fail_closed() -> None:
    stale = assess_capital_rotation(
        _sector_rotation_observations(stale_bucket=CapitalBucket.AI),
        generated_at=NOW,
    )
    rejected = assess_capital_rotation(
        _sector_rotation_observations(
            quality_bucket=CapitalBucket.DEFI, quality=_rejected_quality()
        ),
        generated_at=NOW,
    )

    assert stale.mode is RotationMode.UNKNOWN
    assert "ai capital-flow input is stale" in stale.rejection_reasons
    assert rejected.mode is RotationMode.UNKNOWN
    assert "defi capital-flow quality is rejected" in rejected.rejection_reasons


def test_degraded_rotation_quality_reduces_confidence_and_quality() -> None:
    assessment = assess_capital_rotation(
        _sector_rotation_observations(
            quality_bucket=CapitalBucket.LAYER2, quality=_degraded_quality()
        ),
        generated_at=NOW,
    )

    assert assessment.mode is RotationMode.SECTOR_ROTATION
    assert assessment.quality.is_degraded
    assert not assessment.actionable_context
    assert assessment.confidence == Decimal("0.6617")


def test_low_confidence_policy_fails_closed() -> None:
    assessment = assess_capital_rotation(
        _sector_rotation_observations(),
        generated_at=NOW,
        policy=CapitalRotationPolicy(min_confidence=Decimal("0.95")),
    )

    assert assessment.mode is RotationMode.UNKNOWN
    assert not assessment.actionable_context
    assert "capital rotation confidence is below threshold" in assessment.rejection_reasons


def test_capital_flow_observation_validates_score_bounds() -> None:
    with pytest.raises(ValueError, match="inflow_score must be between 0 and 1"):
        _observation(CapitalBucket.BTC, inflow=Decimal("1.10"))


def test_capital_rotation_assessment_has_no_trading_authority() -> None:
    assessment = assess_capital_rotation(_sector_rotation_observations(), generated_at=NOW)

    with pytest.raises(ValueError, match="cannot create signals"):
        assessment.create_signal()
    with pytest.raises(ValueError, match="cannot create order intents"):
        assessment.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        assessment.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        assessment.submit_order()


def test_public_imports_are_available() -> None:
    from abtp.intelligence import CapitalRotationAssessment, CapitalRotationEvidence, SectorStrength

    assert CapitalRotationAssessment is not None
    assert CapitalRotationEvidence is not None
    assert SectorStrength is not None


def _sector_rotation_observations(
    *,
    stale_bucket: CapitalBucket | None = None,
    quality_bucket: CapitalBucket | None = None,
    quality: DataQualityStatus | None = None,
) -> tuple[CapitalFlowObservation, ...]:
    return (
        _observation(
            CapitalBucket.BTC,
            Decimal("0.55"),
            Decimal("0.40"),
            Decimal("0.55"),
            Decimal("0.80"),
            Decimal("0.58"),
            stale_bucket,
            quality_bucket,
            quality,
        ),
        _observation(
            CapitalBucket.ETH,
            Decimal("0.58"),
            Decimal("0.38"),
            Decimal("0.60"),
            Decimal("0.76"),
            Decimal("0.62"),
            stale_bucket,
            quality_bucket,
            quality,
        ),
        _observation(
            CapitalBucket.STABLECOINS,
            Decimal("0.28"),
            Decimal("0.55"),
            Decimal("0.30"),
            Decimal("0.80"),
            Decimal("0.35"),
            stale_bucket,
            quality_bucket,
            quality,
        ),
        _observation(
            CapitalBucket.AI,
            Decimal("0.86"),
            Decimal("0.18"),
            Decimal("0.82"),
            Decimal("0.72"),
            Decimal("0.86"),
            stale_bucket,
            quality_bucket,
            quality,
        ),
        _observation(
            CapitalBucket.RWA,
            Decimal("0.70"),
            Decimal("0.30"),
            Decimal("0.68"),
            Decimal("0.62"),
            Decimal("0.70"),
            stale_bucket,
            quality_bucket,
            quality,
        ),
        _observation(
            CapitalBucket.LAYER2,
            Decimal("0.65"),
            Decimal("0.35"),
            Decimal("0.64"),
            Decimal("0.66"),
            Decimal("0.68"),
            stale_bucket,
            quality_bucket,
            quality,
        ),
        _observation(
            CapitalBucket.DEFI,
            Decimal("0.60"),
            Decimal("0.36"),
            Decimal("0.62"),
            Decimal("0.64"),
            Decimal("0.64"),
            stale_bucket,
            quality_bucket,
            quality,
        ),
    )


def _risk_off_observations() -> tuple[CapitalFlowObservation, ...]:
    return (
        _observation(
            CapitalBucket.BTC,
            Decimal("0.30"),
            Decimal("0.65"),
            Decimal("0.32"),
            Decimal("0.75"),
            Decimal("0.35"),
        ),
        _observation(
            CapitalBucket.ETH,
            Decimal("0.28"),
            Decimal("0.68"),
            Decimal("0.30"),
            Decimal("0.70"),
            Decimal("0.32"),
        ),
        _observation(
            CapitalBucket.STABLECOINS,
            Decimal("0.88"),
            Decimal("0.15"),
            Decimal("0.82"),
            Decimal("0.85"),
            Decimal("0.86"),
        ),
        _observation(
            CapitalBucket.LARGE_CAPS,
            Decimal("0.25"),
            Decimal("0.70"),
            Decimal("0.28"),
            Decimal("0.62"),
            Decimal("0.30"),
        ),
        _observation(
            CapitalBucket.AI,
            Decimal("0.20"),
            Decimal("0.72"),
            Decimal("0.25"),
            Decimal("0.50"),
            Decimal("0.25"),
        ),
    )


def _observation(
    bucket: CapitalBucket,
    inflow: Decimal,
    outflow: Decimal = Decimal("0.40"),
    momentum: Decimal = Decimal("0.55"),
    liquidity: Decimal = Decimal("0.70"),
    relative_strength: Decimal = Decimal("0.55"),
    stale_bucket: CapitalBucket | None = None,
    quality_bucket: CapitalBucket | None = None,
    quality: DataQualityStatus | None = None,
) -> CapitalFlowObservation:
    return CapitalFlowObservation(
        bucket=bucket,
        inflow_score=inflow,
        outflow_score=outflow,
        momentum_score=momentum,
        liquidity_score=liquidity,
        relative_strength_score=relative_strength,
        quality=quality if bucket is quality_bucket else _trusted_quality(),
        observed_at=NOW,
        source_ref=f"fixture:rotation:{bucket.value}",
        stale=bucket is stale_bucket,
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:rotation",
        checked_at=NOW,
    )


def _degraded_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.DEGRADED,
        issues=(
            DataQualityIssue(
                flag="partial_flow_coverage",
                severity=DataTrustLevel.DEGRADED,
                reason="some optional flow sources are unavailable",
            ),
        ),
        source_ref="fixture:rotation:degraded",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="malformed_flow_payload",
                severity=DataTrustLevel.REJECTED,
                reason="capital-flow payload cannot be trusted",
            ),
        ),
        source_ref="fixture:rotation:rejected",
        checked_at=NOW,
    )
