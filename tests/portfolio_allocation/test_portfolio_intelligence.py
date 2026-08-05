from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, PortfolioPosition, PortfolioSnapshot
from abtp.portfolio import (
    AllocationInput,
    CorrelationEstimate,
    CorrelationSnapshot,
    HedgeRecommendation,
    PortfolioHealth,
    PortfolioIntelligenceInput,
    evaluate_portfolio_intelligence,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_portfolio_intelligence_reports_healthy_state_without_hedge() -> None:
    report = evaluate_portfolio_intelligence(_inputs())

    assert report.health is PortfolioHealth.HEALTHY
    assert report.hedge_recommendation is HedgeRecommendation.NONE
    assert report.health_score == Decimal("0.8100")
    assert report.hedge_pct == Decimal("0")
    assert report.recommended_stablecoin_pct == Decimal("0")
    assert report.acceptable_for_review
    assert report.quality.is_trusted
    assert report.audit_payload()["health"] == "healthy"


def test_cash_reserve_breach_recommends_raise_cash_and_fails_closed() -> None:
    report = evaluate_portfolio_intelligence(
        _inputs(allocation_input=_allocation_input(available_cash=Decimal("100")))
    )

    assert report.health is PortfolioHealth.DEFENSIVE
    assert report.hedge_recommendation is HedgeRecommendation.RAISE_CASH
    assert report.hedge_pct == Decimal("0.2500")
    assert report.recommended_cash_reserve_pct == Decimal("0.35")
    assert not report.acceptable_for_review
    assert report.quality.is_rejected
    assert "cash reserve is below portfolio intelligence floor" in report.rejection_reasons


def test_sector_concentration_recommends_reduce_exposure() -> None:
    report = evaluate_portfolio_intelligence(
        _inputs(sector_exposures={"layer1": Decimal("0.72"), "defi": Decimal("0.10")})
    )

    assert report.health is PortfolioHealth.DEFENSIVE
    assert report.hedge_recommendation is HedgeRecommendation.REDUCE_EXPOSURE
    assert report.max_sector_exposure_pct == Decimal("0.72")
    assert "sector exposure exceeds portfolio intelligence limit" in report.rejection_reasons


def test_rejected_source_quality_requires_manual_review() -> None:
    report = evaluate_portfolio_intelligence(_inputs(quality=_rejected_quality()))

    assert report.health is PortfolioHealth.DEFENSIVE
    assert report.hedge_recommendation is HedgeRecommendation.MANUAL_REVIEW
    assert report.hedge_pct == Decimal("1")
    assert report.quality.is_rejected
    assert "portfolio intelligence source quality is rejected" in report.rejection_reasons


def test_low_diversification_fails_closed_not_executable() -> None:
    report = evaluate_portfolio_intelligence(_inputs(diversification_score=Decimal("0.30")))

    assert report.health is PortfolioHealth.DEFENSIVE
    assert report.quality.is_rejected
    assert not report.acceptable_for_review
    assert "diversification score is below floor" in report.rejection_reasons


def test_portfolio_intelligence_validates_scores() -> None:
    with pytest.raises(ValueError, match="diversification_score must be between 0 and 1"):
        _inputs(diversification_score=Decimal("1.10"))


def test_portfolio_intelligence_has_no_order_or_risk_authority() -> None:
    report = evaluate_portfolio_intelligence(_inputs())

    with pytest.raises(ValueError, match="cannot create order intents"):
        report.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()


def test_public_imports_are_available() -> None:
    from abtp.portfolio import PortfolioIntelligencePolicy, PortfolioIntelligenceReport

    assert PortfolioIntelligencePolicy is not None
    assert PortfolioIntelligenceReport is not None


def _inputs(
    *,
    allocation_input: AllocationInput | None = None,
    sector_exposures: dict[str, Decimal] | None = None,
    asset_risk_scores: dict[str, Decimal] | None = None,
    diversification_score: Decimal = Decimal("0.75"),
    defensive_signal_score: Decimal = Decimal("0.10"),
    confidence_score: Decimal = Decimal("0.75"),
    quality: DataQualityStatus | None = None,
) -> PortfolioIntelligenceInput:
    return PortfolioIntelligenceInput(
        allocation_input=allocation_input or _allocation_input(),
        sector_exposures=sector_exposures or {"layer1": Decimal("0.30"), "defi": Decimal("0.10")},
        asset_risk_scores=asset_risk_scores or {"BTC": Decimal("0.30"), "ETH": Decimal("0.25")},
        diversification_score=diversification_score,
        defensive_signal_score=defensive_signal_score,
        confidence_score=confidence_score,
        quality=quality,
    )


def _allocation_input(*, available_cash: Decimal = Decimal("500")) -> AllocationInput:
    return AllocationInput(
        snapshot=PortfolioSnapshot(
            captured_at=NOW,
            positions=(
                PortfolioPosition(Asset("BTC"), Decimal("0.003"), Asset("USDT"), Decimal("300")),
                PortfolioPosition(Asset("ETH"), Decimal("0.1"), Asset("USDT"), Decimal("200")),
            ),
            source_ref="portfolio:intelligence:fixture",
        ),
        total_equity=Decimal("1000"),
        available_cash=available_cash,
        target_weights={"BTC": Decimal("0.30"), "ETH": Decimal("0.20")},
        generated_at=NOW,
        data_quality=_trusted_quality(),
        confidence_scores={"BTC": Decimal("0.70"), "ETH": Decimal("0.65")},
        volatility_by_asset={"BTC": Decimal("0.04"), "ETH": Decimal("0.05")},
        correlation_snapshot=CorrelationSnapshot(
            generated_at=NOW,
            estimates=(
                CorrelationEstimate(
                    asset_a="BTC",
                    asset_b="ETH",
                    correlation=Decimal("0.20"),
                    sample_count=10,
                ),
            ),
        ),
        source_refs={"portfolio_intelligence": "fixture:portfolio_intelligence"},
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:portfolio_intelligence",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_portfolio_intelligence",
                severity=DataTrustLevel.REJECTED,
                reason="portfolio intelligence fixture is rejected",
            ),
        ),
        source_ref="fixture:portfolio_intelligence:rejected",
        checked_at=NOW,
    )
