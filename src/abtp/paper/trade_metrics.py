"""Fee-inclusive statistics from completed paper positions, not candle returns."""

from collections.abc import Sequence
from decimal import Decimal

from abtp.data import normalize_timestamp
from abtp.domain import OrderSide
from abtp.paper.account import PaperTrade


def closed_trade_pnls(trades: Sequence[PaperTrade]) -> tuple[Decimal, ...]:
    """Combine partial entries/exits into flat-to-flat trades, including both fees."""
    quantity = Decimal("0")
    cash_flow = Decimal("0")
    results: list[Decimal] = []
    for trade in sorted(trades, key=lambda item: normalize_timestamp(item.occurred_at)):
        if (
            not trade.quantity.is_finite()
            or trade.quantity <= 0
            or not trade.price.is_finite()
            or trade.price <= 0
            or not trade.fee_paid.is_finite()
            or trade.fee_paid < 0
        ):
            raise ValueError("paper ledger contains an invalid quantity, price, or fee")
        if trade.side not in (OrderSide.BUY, OrderSide.SELL):
            raise ValueError("paper ledger contains an invalid side")
        if trade.side is OrderSide.BUY:
            quantity += trade.quantity
            cash_flow -= trade.notional + trade.fee_paid
        else:
            if trade.quantity > quantity:
                raise ValueError("paper ledger contains a sell without matching entry quantity")
            quantity -= trade.quantity
            cash_flow += trade.notional - trade.fee_paid
            if quantity == 0:
                results.append(cash_flow)
                cash_flow = Decimal("0")
    return tuple(results)


def trade_metrics(trades: Sequence[PaperTrade]) -> dict[str, str]:
    pnls = closed_trade_pnls(trades)
    count = len(pnls)
    wins = sum(pnl > 0 for pnl in pnls)
    gains = sum((pnl for pnl in pnls if pnl > 0), Decimal("0"))
    losses = -sum((pnl for pnl in pnls if pnl < 0), Decimal("0"))
    return {
        "closed_trade_count": str(count),
        "fill_count": str(len(trades)),
        "win_rate": str(Decimal(wins) / count) if count else "not_available",
        "expectancy": str(sum(pnls, Decimal("0")) / count) if count else "not_available",
        "profit_factor": str(gains / losses) if losses else "not_available",
        "metrics_basis": "completed_positions_after_fees",
        "expectancy_unit": "USDT_per_closed_trade",
    }
