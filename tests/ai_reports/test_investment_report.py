from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.ai import (
    AIInvestmentReport,
    InvestmentReportInput,
    InvestmentReportRecommendation,
    InvestmentReportSection,
    InvestmentReportSectionType,
    InvestmentReportStance,
    generate_investment_report,
    section_from_mapping,
)
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel

NOW = datetime(2026, 1, 25, tzinfo=UTC)


def test_investment_report_generates_explainable_buy_review() -> None:
    report = generate_investment_report(
        InvestmentReportInput(
            asset_symbol="btc",
            generated_at=NOW,
            sections=_sections(),
            expected_return_pct=Decimal("0.08"),
            expected_holding_period="2-4 weeks",
            source_refs={"committee": "fixture:committee"},
        )
    )

    assert report.advisory_only is True
    assert report.actionable_context is True
    assert report.recommendation is InvestmentReportRecommendation.BUY_REVIEW
    assert report.quality.is_trusted
    assert report.scorecard.directional_edge == Decimal("3.6700")
    assert report.scorecard.confidence == Decimal("0.5866")
    assert "spot-only exposure fits cash reserve" in report.portfolio_impact_summary
    assert "committee vote favors accumulation review" in report.why_buy
    assert report.audit_payload()["recommendation"] == "buy_review"


def test_investment_report_render_markdown_is_deterministic() -> None:
    report = generate_investment_report(
        InvestmentReportInput(
            asset_symbol="ETH",
            generated_at=NOW,
            sections=_sections(),
            expected_return_pct=Decimal("0.03"),
            expected_holding_period="1-2 weeks",
        )
    )
    rendered = report.render_markdown()

    assert rendered.startswith("# Institutional Investment Report: ETH")
    assert "## Why Buy" in rendered
    assert "## Why Sell" in rendered
    assert "## Why Hold" in rendered
    assert "No profit is guaranteed" in rendered


def test_investment_report_missing_required_sections_fails_closed() -> None:
    report = generate_investment_report(
        InvestmentReportInput(
            asset_symbol="BTC",
            generated_at=NOW,
            sections=_sections()[:-1],
            expected_return_pct=Decimal("0.08"),
            expected_holding_period="2-4 weeks",
        )
    )

    assert report.recommendation is InvestmentReportRecommendation.NO_DECISION
    assert not report.actionable_context
    assert report.quality.is_rejected
    assert "missing_report_sections" in report.quality.flags
    assert "report quality is rejected" in report.rejection_reasons


def test_investment_report_rejected_section_and_missing_expectations_are_non_actionable() -> None:
    sections = list(_sections())
    sections[7] = _section(
        InvestmentReportSectionType.AI_VOTES,
        "AI Votes",
        InvestmentReportStance.SUPPORTIVE,
        Decimal("0.80"),
        quality=_rejected_quality(),
    )

    report = generate_investment_report(
        InvestmentReportInput(asset_symbol="BTC", generated_at=NOW, sections=tuple(sections))
    )

    assert report.recommendation is InvestmentReportRecommendation.NO_DECISION
    assert report.quality.is_rejected
    assert "rejected_report_sections" in report.quality.flags
    assert "expected return is not supplied" in report.rejection_reasons
    assert "expected holding period is not supplied" in report.rejection_reasons


def test_investment_report_has_no_signal_risk_or_order_authority() -> None:
    report = generate_investment_report(
        InvestmentReportInput(
            asset_symbol="BTC",
            generated_at=NOW,
            sections=_sections(),
            expected_return_pct=Decimal("0.08"),
            expected_holding_period="2-4 weeks",
        )
    )

    with pytest.raises(ValueError, match="cannot create signals"):
        report.create_signal()
    with pytest.raises(ValueError, match="cannot create order intents"):
        report.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()


def test_section_from_mapping_and_public_imports() -> None:
    section = section_from_mapping(
        section_type=InvestmentReportSectionType.MARKET_CYCLE,
        title="Market Cycle",
        summary="cycle fixture",
        stance=InvestmentReportStance.NEUTRAL,
        confidence=Decimal("0.50"),
        quality=_trusted_quality(),
        evidence={"phase": "recovery", "risk": "medium"},
    )

    assert AIInvestmentReport.__name__ == "AIInvestmentReport"
    assert section.evidence_points == ("phase: recovery", "risk: medium")


def _sections() -> tuple[InvestmentReportSection, ...]:
    return (
        _section(
            InvestmentReportSectionType.WHY_BUY,
            "Why Buy",
            InvestmentReportStance.SUPPORTIVE,
            Decimal("0.82"),
            "committee vote favors accumulation review",
        ),
        _section(
            InvestmentReportSectionType.WHY_SELL,
            "Why Sell",
            InvestmentReportStance.OPPOSING,
            Decimal("0.35"),
            "sell case is limited to volatility and macro uncertainty",
        ),
        _section(
            InvestmentReportSectionType.WHY_HOLD,
            "Why Hold",
            InvestmentReportStance.NEUTRAL,
            Decimal("0.55"),
            "hold review remains valid while risk checks are pending",
        ),
        _section(
            InvestmentReportSectionType.MARKET_CYCLE,
            "Market Cycle",
            InvestmentReportStance.SUPPORTIVE,
            Decimal("0.70"),
            "cycle evidence points to recovery",
        ),
        _section(
            InvestmentReportSectionType.MACRO_ANALYSIS,
            "Macro Analysis",
            InvestmentReportStance.NEUTRAL,
            Decimal("0.58"),
            "macro pressure is neutral",
        ),
        _section(
            InvestmentReportSectionType.ONCHAIN,
            "On-chain",
            InvestmentReportStance.SUPPORTIVE,
            Decimal("0.74"),
            "exchange outflows support accumulation review",
        ),
        _section(
            InvestmentReportSectionType.FUNDAMENTALS,
            "Fundamentals",
            InvestmentReportStance.SUPPORTIVE,
            Decimal("0.78"),
            "fundamental rating is strong",
        ),
        _section(
            InvestmentReportSectionType.AI_VOTES,
            "AI Votes",
            InvestmentReportStance.SUPPORTIVE,
            Decimal("0.76"),
            "committee agreement is supportive",
        ),
        _section(
            InvestmentReportSectionType.RISK,
            "Risk",
            InvestmentReportStance.OPPOSING,
            Decimal("0.45"),
            "risk review still limits sizing",
        ),
        _section(
            InvestmentReportSectionType.EXPECTED_RETURN,
            "Expected Return",
            InvestmentReportStance.SUPPORTIVE,
            Decimal("0.67"),
            "expected return is positive after costs",
        ),
        _section(
            InvestmentReportSectionType.EXPECTED_HOLDING,
            "Expected Holding",
            InvestmentReportStance.NEUTRAL,
            Decimal("0.60"),
            "holding period is medium term",
        ),
        _section(
            InvestmentReportSectionType.PORTFOLIO_IMPACT,
            "Portfolio Impact",
            InvestmentReportStance.NEUTRAL,
            Decimal("0.62"),
            "spot-only exposure fits cash reserve",
        ),
    )


def _section(
    section_type: InvestmentReportSectionType,
    title: str,
    stance: InvestmentReportStance,
    confidence: Decimal,
    point: str | None = None,
    *,
    quality: DataQualityStatus | None = None,
) -> InvestmentReportSection:
    return InvestmentReportSection(
        section_type=section_type,
        title=title,
        summary=point or f"{title} fixture summary",
        stance=stance,
        confidence=confidence,
        quality=quality or _trusted_quality(),
        evidence_points=(point or f"{title} fixture evidence",),
        source_refs={section_type.value: f"fixture:{section_type.value}"},
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
                flag="rejected_ai_vote_section",
                severity=DataTrustLevel.REJECTED,
                reason="fixture rejected AI vote section",
            ),
        ),
        source_ref="fixture:rejected",
        checked_at=NOW,
    )
