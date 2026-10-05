"""Read-only exchange evidence after a timeout or restart; never retries orders."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any

from abtp.domain import OrderIntent, OrderSide
from abtp.exchanges.binance_testnet import (
    BinanceSpotTestnetClient,
    TestnetError,
    client_order_id,
)


def reconcile_testnet_order(
    client: BinanceSpotTestnetClient,
    intent: OrderIntent,
    *,
    require_protection: bool = True,
) -> dict[str, Any]:
    """Reconstruct fills and commissions from Binance, not an optimistic local response.

    A matched report is evidence for operator review, not authority to clear a
    durable halt, release an approval, retry an order, or enable real trading.
    """
    reasons: list[str] = []
    fees: dict[str, Decimal] = {}
    filled = Decimal(0)
    net_base = Decimal(0)
    status = "unknown"
    protection = "not_checked"
    symbol = intent.pair.base.symbol + intent.pair.quote.symbol
    try:
        client.require_clock_sync()
        order = client.order(symbol, client_order_id(intent.id))
        status = order.status
        filled = order.filled_quantity
        if order.side != intent.side.value.upper() or order.quantity != intent.quantity:
            raise TestnetError("exchange order does not match the saved intent")
        trades = client.fills(symbol, order.order_id)
        seen: set[str] = set()
        filled_from_trades = Decimal(0)
        quote_from_trades = Decimal(0)
        for trade in trades:
            identifier = str(trade.get("id", ""))
            if not identifier or identifier in seen:
                raise TestnetError("duplicate or missing exchange fill identity")
            seen.add(identifier)
            if trade.get("isBuyer") is not (intent.side is OrderSide.BUY):
                raise TestnetError("fill side does not match the saved intent")
            quantity = _number(trade.get("qty"), positive=True)
            quote = _number(trade.get("quoteQty"), positive=True)
            commission = _number(trade.get("commission"))
            asset = str(trade.get("commissionAsset", ""))
            if not asset:
                raise TestnetError("exchange fee asset is missing")
            filled_from_trades += quantity
            quote_from_trades += quote
            fees[asset] = fees.get(asset, Decimal(0)) + commission
        if filled_from_trades != filled or abs(quote_from_trades - order.quote_quantity) > Decimal(
            "0.00000001"
        ):
            raise TestnetError("exchange fills and order totals have not reconciled")
        net_base = filled - fees.get(intent.pair.base.symbol, Decimal(0))
        if net_base < 0:
            raise TestnetError("base-asset commission exceeds filled quantity")
        if status in {"NEW", "PARTIALLY_FILLED", "PENDING_NEW", "PENDING_CANCEL"}:
            reasons.append("order is not terminal; entries remain blocked")
        if require_protection and intent.side is OrderSide.BUY and net_base > 0:
            rules = client.symbol_rules(symbol)
            lot = next(item for item in rules.filters if item["filterType"] == "LOT_SIZE")
            step = _number(lot["stepSize"], positive=True)
            protected_quantity = (net_base / step).to_integral_value(rounding=ROUND_DOWN) * step
            if protected_quantity <= 0:
                raise TestnetError("filled position is below protectable exchange quantity")
            group = client.order_list(client_order_id(intent.id, "p"))
            if group.get("symbol") != symbol or group.get("contingencyType") != "OCO":
                raise TestnetError("protective order list identity/type mismatch")
            above = client.order(symbol, client_order_id(intent.id, "t"))
            below = client.order(symbol, client_order_id(intent.id, "s"))
            children = group.get("orders")
            if not isinstance(children, list) or {
                (str(item.get("orderId")), str(item.get("clientOrderId")))
                for item in children
                if isinstance(item, dict)
            } != {(above.order_id, above.client_id), (below.order_id, below.client_id)}:
                raise TestnetError("protective orders do not belong to the saved OCO list")
            if (
                above.order_type != "LIMIT_MAKER"
                or below.order_type != "STOP_LOSS"
                or not 0 < below.stop_price < above.price
            ):
                raise TestnetError("protective stop/target order types or prices are invalid")
            for leg in (above, below):
                if leg.side != "SELL" or leg.quantity != protected_quantity:
                    raise TestnetError("protective quantities do not match owned net position")
            exited = above.filled_quantity + below.filled_quantity
            if exited > protected_quantity:
                raise TestnetError("protective fills exceed owned position")
            if (
                group.get("listOrderStatus") == "EXECUTING"
                and below.status == "NEW"
                and above.status == "NEW"
            ):
                protection = "exchange_oco_active"
            elif group.get("listOrderStatus") == "ALL_DONE" and exited == protected_quantity:
                protection = "position_closed_by_oco"
            else:
                raise TestnetError("position protection or exit is not confirmed")
            account = client.account()
            available, locked = account.balances.get(
                intent.pair.base.symbol, (Decimal(0), Decimal(0))
            )
            if available + locked < net_base - exited:
                raise TestnetError("exchange balance is below remaining owned position")
    except (TestnetError, ValueError, KeyError, StopIteration, ArithmeticError) as exc:
        reasons.append(
            str(exc) if isinstance(exc, TestnetError) else "invalid reconciliation evidence"
        )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": "binance_spot_testnet",
        "intent_id": str(intent.id),
        "client_order_id": client_order_id(intent.id),
        "status": status,
        "filled_quantity": str(filled),
        "net_base_after_entry_fees": str(net_base) if intent.side is OrderSide.BUY else None,
        "commissions_by_asset": {asset: str(value) for asset, value in fees.items()},
        "protection": protection,
        "matched": not reasons,
        "blocks_continuation": bool(reasons),
        "reasons": reasons,
        "live_ready": False,
        "real_money_enabled": False,
        "automatic_retries": False,
        "ledger_halt_cleared": False,
    }


def _number(value: Any, *, positive: bool = False) -> Decimal:
    try:
        number = Decimal(str(value))
    except ArithmeticError:
        raise TestnetError("malformed numeric reconciliation evidence") from None
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise TestnetError("invalid numeric reconciliation evidence")
    return number
