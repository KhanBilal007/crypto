from __future__ import annotations

from decimal import Decimal

from abtp.risk import calculate_position_size


def test_position_size_uses_risk_cash_and_exposure_limits() -> None:
    result = calculate_position_size(
        total_equity=Decimal("10000"),
        available_cash=Decimal("8000"),
        current_exposure=Decimal("0"),
        entry_price=Decimal("100"),
        stop_price=Decimal("98"),
        max_risk_per_trade_pct=Decimal("0.01"),
        max_position_pct=Decimal("0.25"),
        min_cash_reserve_pct=Decimal("0.20"),
        fee_bps=Decimal("10"),
        slippage_bps=Decimal("5"),
    )

    assert result.risk_amount == Decimal("100.00")
    assert result.stop_distance == Decimal("2")
    assert result.per_unit_risk == Decimal("2.15")
    assert result.max_notional == Decimal("2500.00")
    assert result.max_quantity == Decimal("25.00")
    assert result.exposure_limited


def test_position_size_can_be_cash_limited() -> None:
    result = calculate_position_size(
        total_equity=Decimal("10000"),
        available_cash=Decimal("2300"),
        current_exposure=Decimal("0"),
        entry_price=Decimal("100"),
        stop_price=Decimal("98"),
        max_risk_per_trade_pct=Decimal("0.01"),
        max_position_pct=Decimal("0.25"),
        min_cash_reserve_pct=Decimal("0.20"),
        fee_bps=Decimal("10"),
        slippage_bps=Decimal("5"),
    )

    assert result.max_notional == Decimal("300.00")
    assert result.max_quantity == Decimal("3.00")
    assert result.cash_limited
