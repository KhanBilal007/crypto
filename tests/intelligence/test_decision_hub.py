from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.intelligence import (
    DecisionEvidence,
    DecisionEvidenceType,
    DecisionHubInput,
    DecisionStance,
    FinalInvestmentDecision,
    build_institutional_decision,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_decision_hub_builds_favorable_explainable_review_record() -> None:
    record = build_institutional_decision(
        DecisionHubInput(
            symbol="btc",
            generated_at=NOW,
            evidence=_required_evidence(),
            source_refs={"cycle": "fixture:stage-070"},
        )
    )

    assert record.final_decision is FinalInvestmentDecision.FAVORABLE_REVIEW
    assert record.actionable_review
    assert record.allocation.symbol == "BTC"
    assert record.allocation.suggested_allocation_pct > Decimal("0")
    assert record.entry_exit_plan.stop_loss_required
    assert record.audit_payload()["evidence_types"].count("|") == 9
    assert record.quality.is_trusted


def test_missing_risk_or_confidence_evidence_fails_closed() -> None:
    evidence = tuple(
        item
        for item in _required_evidence()
        if item.evidence_type
        not in {
            DecisionEvidenceType.RISK_ENGINE,
            DecisionEvidenceType.CONFIDENCE_ENGINE,
        }
    )

    record = build_institutional_decision(
        DecisionHubInput(symbol="BTC", generated_at=NOW, evidence=evidence)
    )

    assert record.final_decision is FinalInvestmentDecision.REJECT_NO_ACTION
    assert not record.actionable_review
    assert record.allocation.suggested_allocation_pct == Decimal("0")
    assert "missing required evidence: risk_engine" in record.rejection_reasons
    assert "confidence engine evidence is below threshold" in record.rejection_reasons


def test_blocking_risk_engine_rejects_new_entries() -> None:
    evidence = tuple(
        _evidence(
            DecisionEvidenceType.RISK_ENGINE,
            summary="risk engine rejected due to drawdown",
            risk=Decimal("0.90"),
            blocking=True,
        )
        if item.evidence_type is DecisionEvidenceType.RISK_ENGINE
        else item
        for item in _required_evidence()
    )

    record = build_institutional_decision(
        DecisionHubInput(symbol="BTC", generated_at=NOW, evidence=evidence)
    )

    assert record.final_decision is FinalInvestmentDecision.REJECT_NO_ACTION
    assert record.risk_assessment.block_new_entries
    assert record.quality.is_rejected
    assert "risk_engine blocks new decision review" in record.rejection_reasons


def test_stale_or_rejected_evidence_is_not_silently_accepted() -> None:
    rejected_quality = DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_decision_fixture",
                severity=DataTrustLevel.REJECTED,
                reason="fixture evidence rejected",
            ),
        ),
        source_ref="fixture:rejected",
        checked_at=NOW,
    )
    evidence = tuple(
        _evidence(
            DecisionEvidenceType.ONCHAIN,
            quality=rejected_quality,
            stale=True,
            summary="on-chain evidence is stale and rejected",
        )
        if item.evidence_type is DecisionEvidenceType.ONCHAIN
        else item
        for item in _required_evidence()
    )

    record = build_institutional_decision(
        DecisionHubInput(symbol="BTC", generated_at=NOW, evidence=evidence)
    )

    assert record.final_decision is FinalInvestmentDecision.REJECT_NO_ACTION
    assert record.quality.is_rejected
    assert "onchain evidence is stale" in record.rejection_reasons
    assert "onchain quality is not trusted" in record.rejection_reasons


def test_low_support_decision_holds_without_allocation() -> None:
    evidence = tuple(
        _evidence(
            item.evidence_type,
            support=Decimal("0.50"),
            confidence=Decimal("0.65"),
            risk=Decimal("0.20"),
            summary=f"{item.evidence_type.value} cautious evidence",
        )
        for item in _required_evidence()
    )

    record = build_institutional_decision(
        DecisionHubInput(symbol="ETH", generated_at=NOW, evidence=evidence)
    )

    assert record.final_decision is FinalInvestmentDecision.HOLD_REVIEW
    assert record.allocation.suggested_allocation_pct == Decimal("0")
    assert not record.actionable_review


def test_decision_record_has_no_signal_risk_order_or_execution_authority() -> None:
    record = build_institutional_decision(
        DecisionHubInput(symbol="BTC", generated_at=NOW, evidence=_required_evidence())
    )

    with pytest.raises(ValueError, match="cannot create strategy signals"):
        record.create_signal(object())
    with pytest.raises(ValueError, match="cannot approve risk"):
        record.approve_risk(object())
    with pytest.raises(ValueError, match="cannot create order intents"):
        record.create_order_intent(object())
    with pytest.raises(ValueError, match="cannot submit orders"):
        record.submit_order(object())
    with pytest.raises(ValueError, match="cannot execute trades"):
        record.execute_trade(object())


def test_public_imports_are_available() -> None:
    import abtp.intelligence as intelligence

    assert intelligence.build_institutional_decision is build_institutional_decision
    assert intelligence.DecisionEvidenceType is DecisionEvidenceType


def _required_evidence() -> tuple[DecisionEvidence, ...]:
    return (
        _evidence(DecisionEvidenceType.MULTI_TIMEFRAME),
        _evidence(DecisionEvidenceType.MARKET_CYCLE, suggested_holding_period="2-6 weeks"),
        _evidence(DecisionEvidenceType.ONCHAIN),
        _evidence(DecisionEvidenceType.FUNDAMENTAL),
        _evidence(DecisionEvidenceType.MACRO_NARRATIVE),
        _evidence(DecisionEvidenceType.AI_COMMITTEE),
        _evidence(DecisionEvidenceType.PORTFOLIO_STATUS),
        _evidence(DecisionEvidenceType.RISK_ENGINE, risk=Decimal("0.20")),
        _evidence(DecisionEvidenceType.OPPORTUNITY_SCANNER),
        _evidence(DecisionEvidenceType.CONFIDENCE_ENGINE, confidence=Decimal("0.76")),
    )


def _evidence(
    evidence_type: DecisionEvidenceType,
    *,
    confidence: Decimal = Decimal("0.74"),
    support: Decimal = Decimal("0.72"),
    risk: Decimal = Decimal("0.24"),
    quality: DataQualityStatus | None = None,
    stale: bool = False,
    blocking: bool = False,
    summary: str | None = None,
    suggested_holding_period: str | None = None,
) -> DecisionEvidence:
    return DecisionEvidence(
        evidence_type=evidence_type,
        source_ref=f"fixture:{evidence_type.value}",
        summary=summary or f"{evidence_type.value} supports operator review",
        confidence=confidence,
        support_score=support,
        risk_score=risk,
        quality=quality or _trusted_quality(evidence_type.value),
        stance=DecisionStance.SUPPORTIVE,
        weight=Decimal("1"),
        blocking=blocking,
        stale=stale,
        suggested_holding_period=suggested_holding_period,
        details={"fixture": evidence_type.value},
    )


def _trusted_quality(source_ref: str) -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref=f"fixture:{source_ref}",
        checked_at=NOW,
    )
