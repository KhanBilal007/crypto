from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain import Asset, PortfolioPosition, PortfolioSnapshot
from abtp.portfolio import (
    AllocationInput,
    AllocationPolicy,
    CorrelationEstimate,
    CorrelationSnapshot,
    RebalanceAction,
    recommend_allocation,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_allocation_recommends_increase_when_safety_gates_pass() -> None:
    recommendation = recommend_allocation(
        _allocation_input(
            target_weights={"BTC": Decimal("0.35"), "ETH": Decimal("0.10")},
            confidence_scores={"BTC": Decimal("0.80"), "ETH": Decimal("0.70")},
        )
    )

    btc_line = _line(recommendation, "BTC")

    assert recommendation.acceptable_for_review
    assert not recommendation.block_expansion
    assert btc_line.action is RebalanceAction.INCREASE
    assert btc_line.recommended_weight == Decimal("0.35")
    assert recommendation.audit_payload()["block_expansion"] == "False"


def test_cash_reserve_breach_blocks_expansion_and_requires_review() -> None:
    recommendation = recommend_allocation(
        _allocation_input(
            available_cash=Decimal("100"),
            target_weights={"BTC": Decimal("0.35")},
        )
    )

    assert recommendation.block_expansion
    assert recommendation.manual_review_required
    assert recommendation.quality.is_rejected
    assert "minimum cash reserve is breached" in recommendation.rejection_reasons
    assert _line(recommendation, "BTC").recommended_weight == Decimal("0.30")


def test_correlation_and_volatility_reduce_asset_expansion() -> None:
    recommendation = recommend_allocation(
        _allocation_input(
            target_weights={"BTC": Decimal("0.35"), "ETH": Decimal("0.20")},
            correlation_snapshot=CorrelationSnapshot(
                generated_at=NOW,
                estimates=(
                    CorrelationEstimate(
                        asset_a="BTC",
                        asset_b="ETH",
                        correlation=Decimal("0.90"),
                        sample_count=10,
                    ),
                ),
            ),
            volatility_by_asset={"ETH": Decimal("0.10")},
        ),
        policy=AllocationPolicy(
            max_correlation=Decimal("0.80"), max_volatility_pct=Decimal("0.08")
        ),
    )

    eth_line = _line(recommendation, "ETH")

    assert eth_line.action is RebalanceAction.HOLD
    assert eth_line.recommended_weight == Decimal("0")
    assert any("correlation" in reason for reason in eth_line.reasons)
    assert any("volatility" in reason for reason in eth_line.reasons)


def test_degraded_data_and_monte_carlo_reduce_allocation_quality() -> None:
    recommendation = recommend_allocation(
        _allocation_input(
            target_weights={"BTC": Decimal("0.35")},
            data_quality=DataQualityStatus(
                trust_level=DataTrustLevel.DEGRADED,
                issues=(
                    DataQualityIssue(
                        flag="portfolio_fixture_degraded",
                        severity=DataTrustLevel.DEGRADED,
                        reason="fixture degraded quality",
                    ),
                ),
                source_ref="fixture:quality",
                checked_at=NOW,
            ),
            monte_carlo_allocation_multiplier=Decimal("0.50"),
        )
    )

    btc_line = _line(recommendation, "BTC")

    assert recommendation.quality.is_degraded
    assert "Monte Carlo risk evidence reduces allocation" in recommendation.reduction_reasons
    assert btc_line.recommended_weight == Decimal("0.175")


def test_drawdown_and_exposure_reject_allocation_expansion() -> None:
    recommendation = recommend_allocation(
        _allocation_input(
            snapshot=PortfolioSnapshot(
                captured_at=NOW,
                positions=(
                    PortfolioPosition(Asset("BTC"), Decimal("1"), Asset("USDT"), Decimal("850")),
                ),
                source_ref="portfolio:fixture",
            ),
            available_cash=Decimal("150"),
            target_weights={"BTC": Decimal("0.90")},
            current_drawdown_pct=Decimal("0.20"),
        ),
        policy=AllocationPolicy(max_gross_exposure_pct=Decimal("0.80")),
    )

    assert recommendation.block_expansion
    assert "drawdown limit is breached" in recommendation.rejection_reasons
    assert "gross exposure limit is breached" in recommendation.rejection_reasons


def test_allocation_recommendation_has_no_order_or_risk_authority() -> None:
    recommendation = recommend_allocation(_allocation_input())

    with pytest.raises(ValueError, match="cannot create order intents"):
        recommendation.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        recommendation.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        recommendation.submit_order()


def _allocation_input(
    *,
    snapshot: PortfolioSnapshot | None = None,
    total_equity: Decimal = Decimal("1000"),
    available_cash: Decimal = Decimal("700"),
    target_weights: dict[str, Decimal] | None = None,
    confidence_scores: dict[str, Decimal] | None = None,
    volatility_by_asset: dict[str, Decimal] | None = None,
    correlation_snapshot: CorrelationSnapshot | None = None,
    data_quality: DataQualityStatus | None = None,
    current_drawdown_pct: Decimal = Decimal("0"),
    monte_carlo_allocation_multiplier: Decimal = Decimal("1"),
) -> AllocationInput:
    return AllocationInput(
        snapshot=snapshot
        or PortfolioSnapshot(
            captured_at=NOW,
            positions=(
                PortfolioPosition(Asset("BTC"), Decimal("0.003"), Asset("USDT"), Decimal("300")),
            ),
            source_ref="portfolio:fixture",
        ),
        total_equity=total_equity,
        available_cash=available_cash,
        target_weights=target_weights or {"BTC": Decimal("0.30")},
        generated_at=NOW,
        data_quality=data_quality or _trusted_quality(),
        current_drawdown_pct=current_drawdown_pct,
        confidence_scores=confidence_scores or {},
        volatility_by_asset=volatility_by_asset or {},
        regime_label="trend_up",
        correlation_snapshot=correlation_snapshot,
        monte_carlo_allocation_multiplier=monte_carlo_allocation_multiplier,
        source_refs={"allocation": "fixture:allocation"},
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:trusted",
        checked_at=NOW,
    )


def _line(recommendation: object, symbol: str) -> object:
    return next(line for line in recommendation.lines if line.asset_symbol == symbol)
