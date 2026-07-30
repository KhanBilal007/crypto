"""Dynamic and ATR trailing stop helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from abtp.data import normalize_timestamp
from abtp.domain import Asset
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class TrailingStopPolicy:
    """Conservative stop parameters for long-only spot position exits."""

    base_stop_loss_pct: Decimal = Decimal("0.03")
    atr_stop_multiplier: Decimal = Decimal("2")
    atr_trailing_multiplier: Decimal = Decimal("3")
    min_stop_distance_pct: Decimal = Decimal("0.005")
    policy_version: str = "stage-046.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("base_stop_loss_pct", self.base_stop_loss_pct),
            ("min_stop_distance_pct", self.min_stop_distance_pct),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.atr_stop_multiplier <= DECIMAL_ZERO:
            raise ValueError("atr_stop_multiplier must be positive")
        if self.atr_trailing_multiplier <= DECIMAL_ZERO:
            raise ValueError("atr_trailing_multiplier must be positive")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class TrailingStopState:
    """Auditable trailing-stop state for one spot position."""

    asset: Asset
    entry_price: Decimal
    highest_price: Decimal
    stop_price: Decimal
    atr: Decimal | None
    updated_at: datetime
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.entry_price, "entry_price"),
            (self.highest_price, "highest_price"),
            (self.stop_price, "stop_price"),
        ):
            if value <= DECIMAL_ZERO:
                raise ValueError(f"{field_name} must be positive")
        if self.atr is not None and self.atr <= DECIMAL_ZERO:
            raise ValueError("atr must be positive when supplied")
        object.__setattr__(self, "updated_at", normalize_timestamp(self.updated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "asset": self.asset.symbol,
            "entry_price": str(self.entry_price),
            "highest_price": str(self.highest_price),
            "stop_price": str(self.stop_price),
            "atr": str(self.atr) if self.atr is not None else None,
            "updated_at": self.updated_at.isoformat(),
            "source_refs": dict(self.source_refs),
        }


def initial_stop_price(
    *,
    entry_price: Decimal,
    atr: Decimal | None = None,
    policy: TrailingStopPolicy | None = None,
) -> Decimal:
    """Return a conservative initial stop using percentage and optional ATR distance."""

    active_policy = policy or TrailingStopPolicy()
    if entry_price <= DECIMAL_ZERO:
        raise ValueError("entry_price must be positive")
    percent_stop = entry_price * (DECIMAL_ONE - active_policy.base_stop_loss_pct)
    if atr is None:
        return percent_stop
    if atr <= DECIMAL_ZERO:
        raise ValueError("atr must be positive when supplied")
    atr_stop = entry_price - atr * active_policy.atr_stop_multiplier
    min_distance_stop = entry_price * (DECIMAL_ONE - active_policy.min_stop_distance_pct)
    return min(percent_stop, atr_stop, min_distance_stop)


def update_atr_trailing_stop(
    state: TrailingStopState,
    *,
    current_price: Decimal,
    atr: Decimal | None,
    updated_at: datetime,
    policy: TrailingStopPolicy | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> TrailingStopState:
    """Update a long-only trailing stop without loosening the existing stop."""

    active_policy = policy or TrailingStopPolicy()
    if current_price <= DECIMAL_ZERO:
        raise ValueError("current_price must be positive")
    if atr is not None and atr <= DECIMAL_ZERO:
        raise ValueError("atr must be positive when supplied")
    highest_price = max(state.highest_price, current_price)
    if atr is None:
        candidate_stop = highest_price * (DECIMAL_ONE - active_policy.base_stop_loss_pct)
    else:
        candidate_stop = highest_price - atr * active_policy.atr_trailing_multiplier
    min_distance_stop = current_price * (DECIMAL_ONE - active_policy.min_stop_distance_pct)
    stop_price = max(state.stop_price, min(candidate_stop, min_distance_stop))
    refs = dict(state.source_refs)
    refs.update(source_refs or {})
    return TrailingStopState(
        asset=state.asset,
        entry_price=state.entry_price,
        highest_price=highest_price,
        stop_price=stop_price,
        atr=atr or state.atr,
        updated_at=updated_at,
        source_refs=refs,
    )
