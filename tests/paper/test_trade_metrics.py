from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from abtp.domain import OrderSide
from abtp.paper.account import PaperTrade
from abtp.paper.trade_metrics import closed_trade_pnls, trade_metrics


def trade(side: OrderSide, quantity: str, price: str, fee: str) -> PaperTrade:
    return PaperTrade(
        uuid4(), side, Decimal(quantity), Decimal(price), Decimal(fee), datetime.now(UTC)
    )


def test_partial_exits_form_one_trade_after_all_fees() -> None:
    trades = (
        trade(OrderSide.BUY, "2", "100", "2"),
        trade(OrderSide.SELL, "1", "110", "1"),
        trade(OrderSide.SELL, "1", "90", "1"),
    )
    assert closed_trade_pnls(trades) == (Decimal("-4"),)
    metrics = trade_metrics(trades)
    assert metrics["closed_trade_count"] == "1"
    assert metrics["fill_count"] == "3"
    assert metrics["win_rate"] == "0"
    assert metrics["expectancy"] == "-4"


def test_open_position_is_not_a_winning_trade_and_unmatched_sell_is_rejected() -> None:
    assert trade_metrics((trade(OrderSide.BUY, "1", "100", "1"),))["win_rate"] == "not_available"
    with pytest.raises(ValueError, match="without matching"):
        closed_trade_pnls((trade(OrderSide.SELL, "1", "100", "1"),))


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", "0"),
        ("quantity", "-1"),
        ("quantity", "NaN"),
        ("price", "0"),
        ("price", "Infinity"),
        ("fee_paid", "-1"),
        ("fee_paid", "NaN"),
    ],
)
def test_invalid_fill_values_are_rejected(field: str, value: str) -> None:
    invalid = replace(trade(OrderSide.BUY, "1", "100", "1"), **{field: Decimal(value)})
    with pytest.raises(ValueError, match="invalid quantity, price, or fee"):
        closed_trade_pnls((invalid,))
