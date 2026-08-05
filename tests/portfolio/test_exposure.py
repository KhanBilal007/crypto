from __future__ import annotations

from decimal import Decimal

from abtp.domain import Asset, PortfolioPosition
from abtp.portfolio import (
    aggregate_exposure,
    cash_reserve_ratio,
    drawdown_limit_breached,
    exposure_limit_breached,
    has_min_cash_reserve,
)


def test_exposure_aggregates_by_asset() -> None:
    summary = aggregate_exposure(
        (
            PortfolioPosition(Asset("BTC"), Decimal("0.1"), Asset("USDT"), Decimal("3000")),
            PortfolioPosition(Asset("BTC"), Decimal("0.2"), Asset("USDT"), Decimal("6000")),
            PortfolioPosition(Asset("ETH"), Decimal("1"), Asset("USDT"), Decimal("2000")),
        ),
        total_equity=Decimal("20000"),
    )

    assert summary.gross_exposure == Decimal("11000")
    assert summary.net_exposure == Decimal("11000")
    assert summary.gross_exposure_pct == Decimal("0.55")
    assert tuple(item.asset.symbol for item in summary.exposures) == ("BTC", "ETH")
    assert summary.exposures[0].quantity == Decimal("0.3")


def test_constraint_helpers_are_deterministic() -> None:
    summary = aggregate_exposure(
        (PortfolioPosition(Asset("BTC"), Decimal("0.5"), Asset("USDT"), Decimal("9000")),),
        total_equity=Decimal("10000"),
    )

    assert cash_reserve_ratio(
        available_cash=Decimal("2500"),
        total_equity=Decimal("10000"),
    ) == Decimal("0.25")
    assert has_min_cash_reserve(
        available_cash=Decimal("2500"),
        total_equity=Decimal("10000"),
        min_cash_reserve_pct=Decimal("0.20"),
    )
    assert exposure_limit_breached(summary, max_gross_exposure_pct=Decimal("0.80"))
    assert drawdown_limit_breached(
        current_drawdown_pct=Decimal("0.12"),
        max_drawdown_pct=Decimal("0.10"),
    )
