from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from abtp.data import DataQualityStatus, DataTrustLevel
from abtp.intelligence import (
    DecisionEvidence,
    DecisionEvidenceType,
    DecisionHubInput,
    DecisionStance,
    FinalInvestmentDecision,
    build_institutional_decision,
)

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_final_readiness_gate_tracks_plan_endpoint_and_current_code_stage() -> None:
    plan = (ROOT / "docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    final_integration = (ROOT / "docs/final_integration.md").read_text(encoding="utf-8")
    release_checklist = (ROOT / "docs/production_release_checklist.md").read_text(encoding="utf-8")

    assert "Stage 070" in plan
    assert "Stage 071" in plan
    assert "Stage 072" in plan
    assert "Stage 073" in plan
    assert "Stage 074" not in plan
    assert "all Stage 005-073 acceptance criteria pass" in plan
    assert "Stage 073: Paper Trading Evaluation Gate." in readme
    assert "Stage 073 ties the completed ABTP foundations" in final_integration
    assert "Stage 073 readiness is controlled" in release_checklist
    assert "Paper command-center BUY REVIEW labels are paper-only" in release_checklist
    assert "Paper runner sessions produce deterministic" in release_checklist
    assert "Paper evaluation gate reports remain paper" in release_checklist


def test_stage070_decision_hub_remains_advisory_at_readiness_gate() -> None:
    record = build_institutional_decision(
        DecisionHubInput(symbol="BTC", generated_at=NOW, evidence=_required_evidence())
    )

    assert record.final_decision is FinalInvestmentDecision.FAVORABLE_REVIEW
    assert record.actionable_review
    assert record.advisory_only
    with pytest.raises(ValueError, match="cannot create strategy signals"):
        record.create_signal(object())
    with pytest.raises(ValueError, match="cannot approve risk"):
        record.approve_risk(object())
    with pytest.raises(ValueError, match="cannot create order intents"):
        record.create_order_intent(object())
    with pytest.raises(ValueError, match="cannot execute trades"):
        record.execute_trade(object())


def _required_evidence() -> tuple[DecisionEvidence, ...]:
    return tuple(
        _evidence(evidence_type)
        for evidence_type in (
            DecisionEvidenceType.MULTI_TIMEFRAME,
            DecisionEvidenceType.MARKET_CYCLE,
            DecisionEvidenceType.ONCHAIN,
            DecisionEvidenceType.FUNDAMENTAL,
            DecisionEvidenceType.MACRO_NARRATIVE,
            DecisionEvidenceType.AI_COMMITTEE,
            DecisionEvidenceType.PORTFOLIO_STATUS,
            DecisionEvidenceType.RISK_ENGINE,
            DecisionEvidenceType.OPPORTUNITY_SCANNER,
            DecisionEvidenceType.CONFIDENCE_ENGINE,
        )
    )


def _evidence(evidence_type: DecisionEvidenceType) -> DecisionEvidence:
    return DecisionEvidence(
        evidence_type=evidence_type,
        source_ref=f"stage070:{evidence_type.value}",
        summary=f"{evidence_type.value} fixture supports operator review",
        confidence=Decimal("0.72"),
        support_score=Decimal("0.72"),
        risk_score=Decimal("0.20"),
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref=f"stage070:{evidence_type.value}",
            checked_at=NOW,
        ),
        stance=DecisionStance.SUPPORTIVE,
    )
