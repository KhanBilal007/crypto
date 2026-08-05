from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.confidence import (
    ConfidenceComponent,
    ConfidenceComponentInput,
    ConfidenceScoringInput,
    ConfidenceStance,
    aggregate_confidence,
)
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_weighted_aggregation_includes_all_component_contributions() -> None:
    result = aggregate_confidence(_scoring_input(confidence=Decimal("0.80")))

    assert result.score == Decimal("0.8000")
    assert result.actionable
    assert result.included_weight == Decimal("1.0000")
    assert len(result.contributions) == 12
    assert result.audit_payload()["included_components"].startswith("trend|momentum")
    assert result.as_dict()["quality"] == "trusted"


def test_missing_optional_context_reduces_score_but_can_remain_actionable() -> None:
    result = aggregate_confidence(
        _scoring_input(
            confidence=Decimal("0.80"),
            omitted={
                ConfidenceComponent.SENTIMENT,
                ConfidenceComponent.ONCHAIN_CONTEXT,
            },
        )
    )

    assert result.score == Decimal("0.7200")
    assert result.actionable
    assert result.quality.is_degraded
    assert "confidence component sentiment is missing" in result.non_actionable_reasons
    assert "confidence component sentiment is missing" not in result.rejected_reasons


def test_missing_required_component_is_non_actionable() -> None:
    result = aggregate_confidence(
        _scoring_input(confidence=Decimal("0.80"), omitted={ConfidenceComponent.RISK_CONTEXT})
    )

    assert not result.actionable
    assert result.quality.is_rejected
    assert "confidence component risk_context is missing" in result.rejected_reasons


def test_degraded_quality_reduces_component_contribution() -> None:
    result = aggregate_confidence(
        _scoring_input(
            confidence=Decimal("0.80"),
            overrides={
                ConfidenceComponent.ORDER_BOOK: ConfidenceComponentInput(
                    component=ConfidenceComponent.ORDER_BOOK,
                    confidence=Decimal("0.80"),
                    quality=_degraded_quality(),
                    source_ref="fixture:order_book",
                    rationale="order book is degraded but usable",
                )
            },
        )
    )

    contribution = _contribution(result, ConfidenceComponent.ORDER_BOOK)

    assert result.score == Decimal("0.7640")
    assert contribution.included
    assert contribution.effective_confidence == Decimal("0.4000")
    assert result.quality.is_degraded


def test_rejected_or_stale_component_fails_closed() -> None:
    result = aggregate_confidence(
        _scoring_input(
            confidence=Decimal("0.80"),
            overrides={
                ConfidenceComponent.DATA_QUALITY: ConfidenceComponentInput(
                    component=ConfidenceComponent.DATA_QUALITY,
                    confidence=Decimal("0.90"),
                    quality=_rejected_quality(),
                    source_ref="fixture:data_quality",
                    rationale="data quality rejected",
                    stale=True,
                )
            },
        )
    )

    assert not result.actionable
    assert result.quality.is_rejected
    assert "confidence component data_quality quality is rejected" in result.rejected_reasons
    assert "confidence component data_quality is stale" in result.rejected_reasons
    assert not _contribution(result, ConfidenceComponent.DATA_QUALITY).included


def test_component_disagreement_is_rejected() -> None:
    result = aggregate_confidence(
        _scoring_input(
            confidence=Decimal("0.80"),
            overrides={
                ConfidenceComponent.TREND: _component(
                    ConfidenceComponent.TREND,
                    Decimal("0.90"),
                    stance=ConfidenceStance.SUPPORTIVE,
                ),
                ConfidenceComponent.AI_PREDICTION: _component(
                    ConfidenceComponent.AI_PREDICTION,
                    Decimal("0.85"),
                    stance=ConfidenceStance.OPPOSING,
                ),
            },
        )
    )

    assert not result.actionable
    assert "supportive and opposing confidence components disagree" in result.rejected_reasons


def test_exchange_health_and_risk_context_block_actionability() -> None:
    result = aggregate_confidence(
        _scoring_input(
            confidence=Decimal("0.90"),
            exchange_health_blocked=True,
            exchange_health_reasons=("exchange health blocks new entries",),
            risk_rejected=True,
            risk_reasons=("drawdown limit breached",),
        )
    )

    assert not result.actionable
    assert "exchange health blocks new entries" in result.rejected_reasons
    assert "drawdown limit breached" in result.rejected_reasons


def test_confidence_result_has_no_signal_order_or_risk_authority() -> None:
    result = aggregate_confidence(_scoring_input())

    with pytest.raises(ValueError, match="cannot create signals"):
        result.create_signal()
    with pytest.raises(ValueError, match="cannot create order intents"):
        result.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        result.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        result.submit_order()


def _scoring_input(
    *,
    confidence: Decimal = Decimal("0.75"),
    omitted: set[ConfidenceComponent] | None = None,
    overrides: dict[ConfidenceComponent, ConfidenceComponentInput] | None = None,
    exchange_health_blocked: bool = False,
    exchange_health_reasons: tuple[str, ...] = (),
    risk_rejected: bool = False,
    risk_reasons: tuple[str, ...] = (),
) -> ConfidenceScoringInput:
    omitted = omitted or set()
    overrides = overrides or {}
    components = tuple(
        overrides.get(component) or _component(component, confidence)
        for component in ConfidenceComponent
        if component not in omitted
    )
    return ConfidenceScoringInput(
        generated_at=NOW,
        components=components,
        feature_schema_version="stage-015.v1",
        exchange_health_blocked=exchange_health_blocked,
        exchange_health_reasons=exchange_health_reasons,
        risk_rejected=risk_rejected,
        risk_reasons=risk_reasons,
        source_refs={"confidence": "fixture:confidence"},
    )


def _component(
    component: ConfidenceComponent,
    confidence: Decimal,
    *,
    stance: ConfidenceStance = ConfidenceStance.NEUTRAL,
) -> ConfidenceComponentInput:
    return ConfidenceComponentInput(
        component=component,
        confidence=confidence,
        quality=_trusted_quality(),
        source_ref=f"fixture:{component.value}",
        rationale=f"{component.value} fixture confidence",
        stance=stance,
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


def _contribution(result: object, component: ConfidenceComponent) -> object:
    return next(item for item in result.contributions if item.component is component)
