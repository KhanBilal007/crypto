"""Preflight validation for supervised live order previews."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from abtp.data import normalize_timestamp
from abtp.domain import OrderIntent, OrderSide
from abtp.risk import assert_order_intent_has_approved_risk
from abtp.security import (
    ExchangeKeyPermissions,
    ExchangeKeyPolicy,
    validate_exchange_key_permissions,
)


@dataclass(frozen=True, slots=True)
class LivePreflightConfig:
    """Tiny-position live preflight limits."""

    max_risk_per_trade_pct: Decimal = Decimal("0.0025")
    max_open_live_positions: int = 1
    max_order_notional: Decimal = Decimal("25")
    max_spread_bps: Decimal = Decimal("50")
    max_slippage_bps: Decimal = Decimal("25")

    def __post_init__(self) -> None:
        if not Decimal("0") < self.max_risk_per_trade_pct <= Decimal("1"):
            raise ValueError("max_risk_per_trade_pct must be between 0 and 1")
        if self.max_open_live_positions < 0:
            raise ValueError("max_open_live_positions cannot be negative")
        if self.max_order_notional <= Decimal("0"):
            raise ValueError("max_order_notional must be positive")
        if self.max_spread_bps < Decimal("0") or self.max_slippage_bps < Decimal("0"):
            raise ValueError("spread/slippage limits cannot be negative")


@dataclass(frozen=True, slots=True)
class LiveMarketPreflight:
    """Live order preview inputs from adapters and security validation."""

    price: Decimal
    quote_balance_available: Decimal
    account_equity: Decimal
    fee_bps: Decimal
    spread_bps: Decimal
    slippage_bps: Decimal
    open_live_positions: int
    permissions: ExchangeKeyPermissions
    checked_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "checked_at", normalize_timestamp(self.checked_at))
        if self.price <= Decimal("0"):
            raise ValueError("price must be positive")
        if self.quote_balance_available < Decimal("0"):
            raise ValueError("quote_balance_available cannot be negative")
        if self.account_equity <= Decimal("0"):
            raise ValueError("account_equity must be positive")
        if self.fee_bps < Decimal("0") or self.spread_bps < Decimal("0"):
            raise ValueError("fee_bps and spread_bps cannot be negative")
        if self.slippage_bps < Decimal("0"):
            raise ValueError("slippage_bps cannot be negative")
        if self.open_live_positions < 0:
            raise ValueError("open_live_positions cannot be negative")


@dataclass(frozen=True, slots=True)
class LiveOrderPreview:
    """Auditable preview for one supervised live order."""

    order_intent_id: str
    estimated_price: Decimal
    estimated_notional: Decimal
    estimated_fee: Decimal
    spread_bps: Decimal
    slippage_bps: Decimal
    max_risk_notional: Decimal
    quote_balance_available: Decimal
    open_live_positions: int
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class LivePreflightResult:
    """Preflight validation result."""

    allowed: bool
    reasons: tuple[str, ...]
    preview: LiveOrderPreview

    def require_allowed(self) -> None:
        if not self.allowed:
            raise PermissionError("; ".join(self.reasons))


def run_live_preflight(
    intent: OrderIntent,
    market: LiveMarketPreflight,
    *,
    config: LivePreflightConfig | None = None,
) -> LivePreflightResult:
    """Validate tiny supervised live order assumptions before submission."""

    active_config = config or LivePreflightConfig()
    estimated_notional = intent.quantity * market.price
    estimated_fee = estimated_notional * market.fee_bps / Decimal("10000")
    max_risk_notional = min(
        active_config.max_order_notional,
        market.account_equity * active_config.max_risk_per_trade_pct,
    )
    preview = LiveOrderPreview(
        order_intent_id=str(intent.id),
        estimated_price=market.price,
        estimated_notional=estimated_notional,
        estimated_fee=estimated_fee,
        spread_bps=market.spread_bps,
        slippage_bps=market.slippage_bps,
        max_risk_notional=max_risk_notional,
        quote_balance_available=market.quote_balance_available,
        open_live_positions=market.open_live_positions,
        checked_at=market.checked_at,
    )
    reasons: list[str] = []
    try:
        assert_order_intent_has_approved_risk(intent)
    except ValueError as exc:
        reasons.append(str(exc))
    if intent.side is not OrderSide.BUY:
        reasons.append("supervised live gateway supports spot buy orders only")
    if intent.quantity > (
        intent.risk_decision.max_position_size if intent.risk_decision else Decimal("0")
    ):
        reasons.append("order quantity exceeds risk-approved max position size")
    if estimated_notional > max_risk_notional:
        reasons.append("order notional exceeds tiny live risk limit")
    if estimated_notional + estimated_fee > market.quote_balance_available:
        reasons.append("insufficient live quote balance for preview")
    if market.open_live_positions >= active_config.max_open_live_positions:
        reasons.append("maximum open live positions reached")
    if market.spread_bps > active_config.max_spread_bps:
        reasons.append("live spread exceeds preflight limit")
    if market.slippage_bps > active_config.max_slippage_bps:
        reasons.append("live slippage exceeds preflight limit")
    permission_result = validate_exchange_key_permissions(
        market.permissions,
        policy=ExchangeKeyPolicy(require_ip_allowlist=True),
    )
    reasons.extend(permission_result.reasons)
    return LivePreflightResult(
        allowed=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
        preview=preview,
    )
