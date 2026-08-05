from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain import Asset
from abtp.portfolio.accounting import PositionCostBasis
from abtp.risk import (
    ExitAction,
    ExitQualityPolicy,
    PositionExitInput,
    PositionExitPolicy,
    recommend_position_exit,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_partial_profit_recommendation_is_advisory_and_explainable() -> None:
    recommendation = recommend_position_exit(
        _inputs(current_price=Decimal("108"), opened_at=NOW - timedelta(days=2)),
        policy=PositionExitPolicy(partial_profit_pct=Decimal("0.05")),
    )

    assert recommendation.action is ExitAction.PARTIAL_PROFIT
    assert recommendation.recommended_exit_fraction == Decimal("0.50")
    assert recommendation.tighten_stops
    assert not recommendation.block_holding
    assert "partial profit threshold reached" in recommendation.reasons
    assert recommendation.audit_payload()["action"] == "partial_profit"


def test_stop_breach_recommends_exit_review_and_blocks_holding() -> None:
    recommendation = recommend_position_exit(
        _inputs(current_price=Decimal("94"), current_stop_price=Decimal("95")),
    )

    assert recommendation.action is ExitAction.EXIT_POSITION
    assert recommendation.recommended_exit_fraction == Decimal("1")
    assert recommendation.block_holding
    assert recommendation.quality.is_rejected
    assert "current price is at or below stop price" in recommendation.reasons


def test_high_volatility_tightens_stop_without_order_creation() -> None:
    recommendation = recommend_position_exit(
        _inputs(
            current_price=Decimal("110"),
            atr=Decimal("7"),
            current_stop_price=Decimal("100"),
            regime_label="high_volatility",
        )
    )

    assert recommendation.action is ExitAction.TIGHTEN_STOP
    assert recommendation.stop_price > Decimal("100")
    assert recommendation.tighten_stops
    assert recommendation.recommended_exit_fraction == Decimal("0")


def test_time_exit_recommends_full_exit_review() -> None:
    recommendation = recommend_position_exit(
        _inputs(opened_at=NOW - timedelta(days=20)),
        policy=PositionExitPolicy(max_holding_period=timedelta(days=14)),
    )

    assert recommendation.action is ExitAction.EXIT_POSITION
    assert recommendation.block_holding
    assert "maximum holding period reached" in recommendation.reasons


def test_rejected_source_quality_fails_safe_to_manual_review() -> None:
    recommendation = recommend_position_exit(
        _inputs(
            source_quality=DataQualityStatus(
                trust_level=DataTrustLevel.REJECTED,
                issues=(
                    DataQualityIssue(
                        flag="rejected_market_data",
                        severity=DataTrustLevel.REJECTED,
                        reason="fixture rejected data",
                    ),
                ),
                source_ref="fixture:quality",
                checked_at=NOW,
            )
        )
    )

    assert recommendation.action is ExitAction.MANUAL_REVIEW
    assert recommendation.block_holding
    assert recommendation.quality.is_rejected
    assert "source quality is rejected; holding is non-actionable" in recommendation.reasons


def test_exit_recommendation_has_no_execution_or_risk_authority() -> None:
    recommendation = recommend_position_exit(_inputs())

    with pytest.raises(ValueError, match="cannot submit orders"):
        recommendation.submit_order()
    with pytest.raises(ValueError, match="cannot cancel orders"):
        recommendation.cancel_order()
    with pytest.raises(ValueError, match="cannot approve risk"):
        recommendation.approve_risk()


def test_wide_stop_exit_quality_is_degraded() -> None:
    recommendation = recommend_position_exit(
        _inputs(current_price=Decimal("120"), current_stop_price=Decimal("100")),
        policy=PositionExitPolicy(
            partial_profit_pct=Decimal("0.30"),
            quality_policy=ExitQualityPolicy(max_stop_distance_pct=Decimal("0.05")),
        ),
    )

    assert recommendation.quality_report.quality.is_degraded
    assert "stop distance is wide relative to current price" in (
        recommendation.quality_report.warning_reasons
    )


def _inputs(
    *,
    current_price: Decimal = Decimal("102"),
    atr: Decimal | None = Decimal("3"),
    current_stop_price: Decimal | None = None,
    opened_at: datetime | None = None,
    regime_label: str = "trend_up",
    source_quality: DataQualityStatus | None = None,
) -> PositionExitInput:
    return PositionExitInput(
        position=PositionCostBasis(
            asset=Asset("BTC"),
            quantity=Decimal("0.5"),
            average_entry_price=Decimal("100"),
            quote_asset=Asset("USDT"),
        ),
        current_price=current_price,
        evaluated_at=NOW,
        source_quality=source_quality or _trusted_quality(),
        atr=atr,
        current_stop_price=current_stop_price,
        opened_at=opened_at,
        highest_price=max(Decimal("100"), current_price),
        regime_label=regime_label,
        volatility_regime=regime_label,
        source_refs={"position": "fixture:position"},
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:trusted",
        checked_at=NOW,
    )
