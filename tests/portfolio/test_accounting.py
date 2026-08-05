from __future__ import annotations

from decimal import Decimal

import pytest

from abtp.domain import Asset
from abtp.portfolio import (
    PositionCostBasis,
    calculate_drawdown,
    calculate_realized_pnl,
    calculate_unrealized_pnl,
    reserve_open_order_cash,
)


def test_unrealized_and_realized_pnl_include_costs() -> None:
    btc = Asset("BTC")
    position = PositionCostBasis(
        asset=btc,
        quantity=Decimal("0.5"),
        average_entry_price=Decimal("20000"),
        quote_asset=Asset("USDT"),
    )

    unrealized = calculate_unrealized_pnl(position, market_price=Decimal("22000"))
    realized = calculate_realized_pnl(
        asset=btc,
        quantity=Decimal("0.5"),
        entry_price=Decimal("20000"),
        exit_price=Decimal("22000"),
        fee_bps=Decimal("10"),
    )

    assert unrealized.cost_basis == Decimal("10000.0")
    assert unrealized.market_value == Decimal("11000.0")
    assert unrealized.unrealized_pnl == Decimal("1000.0")
    assert unrealized.unrealized_pnl_pct == Decimal("0.1")
    assert realized.gross_pnl == Decimal("1000.0")
    assert realized.fees_paid == Decimal("21.0")
    assert realized.net_pnl == Decimal("979.0")


def test_drawdown_uses_peak_to_trough() -> None:
    drawdown = calculate_drawdown(
        (Decimal("10000"), Decimal("11000"), Decimal("9000"), Decimal("9500"))
    )

    assert drawdown == Decimal("0.1818181818181818181818181818")


def test_open_order_reservation_includes_fee_buffer() -> None:
    reservation = reserve_open_order_cash(
        available_cash=Decimal("2000"),
        quote_asset=Asset("USDT"),
        order_notional=Decimal("1000"),
        fee_bps=Decimal("10"),
        order_ref="order-1",
    )

    assert reservation.fee_buffer == Decimal("1")
    assert reservation.reserved_cash == Decimal("1001")
    with pytest.raises(ValueError, match="insufficient available cash"):
        reserve_open_order_cash(
            available_cash=Decimal("1000"),
            quote_asset=Asset("USDT"),
            order_notional=Decimal("1000"),
            fee_bps=Decimal("10"),
            order_ref="order-2",
        )
