from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain import Asset
from abtp.portfolio.accounting import PositionCostBasis
from abtp.risk import (
    AdaptivePositionInput,
    HoldingRecommendation,
    PositionExitInput,
    manage_adaptive_position,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_adaptive_position_holds_with_low_risk_and_normal_confidence() -> None:
    recommendation = manage_adaptive_position(
        _adaptive_inputs(confidence_score=Decimal("0.62"), scaling_score=Decimal("0"))
    )

    assert recommendation.recommendation is HoldingRecommendation.HOLD
    assert recommendation.hold_pct == Decimal("1")
    assert recommendation.sell_pct == Decimal("0")
    assert recommendation.increase_pct == Decimal("0")
    assert recommendation.exit_pct == Decimal("0")
    assert recommendation.actionable_context
    assert recommendation.quality.is_trusted
    assert recommendation.audit_payload()["recommendation"] == "hold"


def test_high_confidence_low_risk_allows_increase_review_only() -> None:
    recommendation = manage_adaptive_position(
        _adaptive_inputs(
            confidence_score=Decimal("0.82"),
            scaling_score=Decimal("0.80"),
            volatility_score=Decimal("0.20"),
            regime_risk_score=Decimal("0.20"),
        )
    )

    assert recommendation.recommendation is HoldingRecommendation.INCREASE_REVIEW
    assert recommendation.hold_pct == Decimal("1")
    assert recommendation.increase_pct == Decimal("0.1200")
    assert recommendation.sell_pct == Decimal("0")
    assert recommendation.exit_pct == Decimal("0")
    assert not recommendation.actionable_context


def test_partial_profit_carries_into_reduce_recommendation() -> None:
    recommendation = manage_adaptive_position(
        _adaptive_inputs(current_price=Decimal("108"), opened_at=NOW - timedelta(days=2))
    )

    assert recommendation.recommendation is HoldingRecommendation.REDUCE
    assert recommendation.sell_pct == Decimal("0.5000")
    assert recommendation.hold_pct == Decimal("0.5000")
    assert recommendation.exit_pct == Decimal("0")
    assert recommendation.quality.is_degraded
    assert "partial profit recommendation carries into sell percentage" in recommendation.reasons


def test_low_confidence_recommends_reduction() -> None:
    recommendation = manage_adaptive_position(
        _adaptive_inputs(confidence_score=Decimal("0.25"), scaling_score=Decimal("0"))
    )

    assert recommendation.recommendation is HoldingRecommendation.REDUCE
    assert recommendation.sell_pct == Decimal("0.2500")
    assert recommendation.hold_pct == Decimal("0.7500")
    assert "confidence exit threshold recommends reduction" in recommendation.reasons


def test_stop_breach_forces_exit_review() -> None:
    recommendation = manage_adaptive_position(
        _adaptive_inputs(current_price=Decimal("94"), current_stop_price=Decimal("95"))
    )

    assert recommendation.recommendation is HoldingRecommendation.EXIT_REVIEW
    assert recommendation.exit_pct == Decimal("1")
    assert recommendation.hold_pct == Decimal("0")
    assert recommendation.quality.is_rejected


def test_rejected_source_quality_fails_closed_to_exit_review() -> None:
    recommendation = manage_adaptive_position(_adaptive_inputs(source_quality=_rejected_quality()))

    assert recommendation.recommendation is HoldingRecommendation.EXIT_REVIEW
    assert recommendation.exit_pct == Decimal("1")
    assert not recommendation.actionable_context
    assert recommendation.quality.is_rejected


def test_adaptive_input_validates_score_bounds() -> None:
    with pytest.raises(ValueError, match="confidence_score must be between 0 and 1"):
        _adaptive_inputs(confidence_score=Decimal("1.10"))


def test_adaptive_position_has_no_trading_authority() -> None:
    recommendation = manage_adaptive_position(_adaptive_inputs())

    with pytest.raises(ValueError, match="cannot create signals"):
        recommendation.create_signal()
    with pytest.raises(ValueError, match="cannot create order intents"):
        recommendation.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        recommendation.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        recommendation.submit_order()


def test_public_imports_are_available() -> None:
    from abtp.risk import AdaptivePositionRecommendation

    assert AdaptivePositionRecommendation is not None


def _adaptive_inputs(
    *,
    current_price: Decimal = Decimal("102"),
    current_stop_price: Decimal | None = None,
    opened_at: datetime | None = NOW - timedelta(days=3),
    confidence_score: Decimal = Decimal("0.60"),
    volatility_score: Decimal = Decimal("0.25"),
    regime_risk_score: Decimal = Decimal("0.25"),
    scaling_score: Decimal = Decimal("0.20"),
    source_quality: DataQualityStatus | None = None,
) -> AdaptivePositionInput:
    return AdaptivePositionInput(
        exit_input=PositionExitInput(
            position=PositionCostBasis(
                asset=Asset("BTC"),
                quantity=Decimal("0.5"),
                average_entry_price=Decimal("100"),
                quote_asset=Asset("USDT"),
            ),
            current_price=current_price,
            evaluated_at=NOW,
            source_quality=source_quality or _trusted_quality(),
            atr=Decimal("3"),
            current_stop_price=current_stop_price,
            opened_at=opened_at,
            highest_price=max(Decimal("100"), current_price),
            regime_label="trend_up",
            volatility_regime="normal",
            source_refs={"position": "fixture:adaptive_position"},
        ),
        confidence_score=confidence_score,
        volatility_score=volatility_score,
        regime_risk_score=regime_risk_score,
        scaling_score=scaling_score,
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:adaptive_position",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_position_context",
                severity=DataTrustLevel.REJECTED,
                reason="position context cannot be trusted",
            ),
        ),
        source_ref="fixture:adaptive_position:rejected",
        checked_at=NOW,
    )
