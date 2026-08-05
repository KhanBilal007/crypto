from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.confidence import (
    ConfidenceComponent,
    ConfidenceComponentInput,
    ConfidenceReason,
    ConfidenceRejectionReason,
    ConfidenceScoringInput,
    ConfidenceWeightPolicy,
    aggregate_confidence,
)
from abtp.confidence.reasons import quality_from_reasons
from abtp.data import DataQualityStatus, DataTrustLevel

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_weight_policy_rejects_invalid_weights() -> None:
    with pytest.raises(ValueError, match="confidence weights cannot be negative"):
        ConfidenceWeightPolicy(
            component_weights={
                ConfidenceComponent.TREND: Decimal("-0.1"),
                ConfidenceComponent.RISK_CONTEXT: Decimal("1"),
            }
        )


def test_weight_policy_requires_configured_required_components() -> None:
    with pytest.raises(ValueError, match="required components must have configured weights"):
        ConfidenceWeightPolicy(
            component_weights={ConfidenceComponent.TREND: Decimal("1")},
            required_components=(ConfidenceComponent.RISK_CONTEXT,),
        )


def test_reason_quality_marks_degraded_non_rejected_reasons() -> None:
    quality = quality_from_reasons(
        (
            ConfidenceReason(
                category=ConfidenceRejectionReason.MISSING_REQUIRED_COMPONENT,
                message="optional component missing",
                rejected=False,
            ),
        ),
        checked_at=NOW,
        source_ref="fixture:confidence",
    )

    assert quality.is_degraded
    assert quality.flags == ("confidence_missing_required_component",)


def test_duplicate_component_input_is_rejected() -> None:
    component = ConfidenceComponentInput(
        component=ConfidenceComponent.TREND,
        confidence=Decimal("0.80"),
        quality=_trusted_quality(),
        source_ref="fixture:trend",
        rationale="trend fixture",
    )

    with pytest.raises(ValueError, match="duplicate confidence component"):
        ConfidenceScoringInput(generated_at=NOW, components=(component, component))


def test_public_imports_are_available() -> None:
    from abtp.confidence import ConfidenceScoreResult, ConfidenceStance

    assert ConfidenceScoreResult is not None
    assert ConfidenceStance.NEUTRAL.value == "neutral"
    assert aggregate_confidence is not None


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:trusted",
        checked_at=NOW,
    )
