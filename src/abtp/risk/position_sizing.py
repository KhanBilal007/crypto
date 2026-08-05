"""Deterministic position sizing helpers for risk decisions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PositionSizeResult:
    """Calculated maximum position size under configured risk limits."""

    max_quantity: Decimal
    max_notional: Decimal
    risk_amount: Decimal
    per_unit_risk: Decimal
    stop_distance: Decimal
    cash_limited: bool
    exposure_limited: bool

    @property
    def approved_capacity(self) -> bool:
        return self.max_quantity > Decimal("0") and self.max_notional > Decimal("0")


def calculate_position_size(
    *,
    total_equity: Decimal,
    available_cash: Decimal,
    current_exposure: Decimal,
    entry_price: Decimal,
    stop_price: Decimal,
    max_risk_per_trade_pct: Decimal,
    max_position_pct: Decimal,
    min_cash_reserve_pct: Decimal,
    fee_bps: Decimal,
    slippage_bps: Decimal,
) -> PositionSizeResult:
    """Calculate a conservative max quantity from risk and cash constraints."""

    _require_positive(total_equity, "total_equity")
    _require_positive(entry_price, "entry_price")
    _require_positive(stop_price, "stop_price")
    if available_cash < Decimal("0") or current_exposure < Decimal("0"):
        raise ValueError("available_cash and current_exposure cannot be negative")
    for value, field_name in (
        (max_risk_per_trade_pct, "max_risk_per_trade_pct"),
        (max_position_pct, "max_position_pct"),
        (min_cash_reserve_pct, "min_cash_reserve_pct"),
    ):
        if not Decimal("0") <= value <= Decimal("1"):
            raise ValueError(f"{field_name} must be between 0 and 1")
    if fee_bps < Decimal("0") or slippage_bps < Decimal("0"):
        raise ValueError("fee_bps and slippage_bps cannot be negative")

    stop_distance = abs(entry_price - stop_price)
    fee_slippage_buffer = entry_price * (fee_bps + slippage_bps) / Decimal("10000")
    per_unit_risk = stop_distance + fee_slippage_buffer
    if per_unit_risk <= Decimal("0"):
        raise ValueError("per-unit risk must be positive")

    risk_amount = total_equity * max_risk_per_trade_pct
    quantity_by_risk = risk_amount / per_unit_risk
    max_position_notional = max(Decimal("0"), total_equity * max_position_pct - current_exposure)
    spendable_cash = max(Decimal("0"), available_cash - total_equity * min_cash_reserve_pct)
    max_notional = min(quantity_by_risk * entry_price, max_position_notional, spendable_cash)
    max_quantity = max_notional / entry_price if max_notional > Decimal("0") else Decimal("0")
    return PositionSizeResult(
        max_quantity=max_quantity,
        max_notional=max_notional,
        risk_amount=risk_amount,
        per_unit_risk=per_unit_risk,
        stop_distance=stop_distance,
        cash_limited=spendable_cash <= min(quantity_by_risk * entry_price, max_position_notional),
        exposure_limited=max_position_notional
        <= min(quantity_by_risk * entry_price, spendable_cash),
    )


def _require_positive(value: Decimal, field_name: str) -> None:
    if value <= Decimal("0"):
        raise ValueError(f"{field_name} must be positive")
