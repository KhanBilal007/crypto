"""Circuit breakers for limited automation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CircuitBreakerConfig:
    """Fail-closed automation stop thresholds."""

    max_daily_loss_pct: Decimal = Decimal("0.03")
    max_weekly_loss_pct: Decimal = Decimal("0.07")
    max_drawdown_pct: Decimal = Decimal("0.10")
    max_spread_bps: Decimal = Decimal("75")
    max_consecutive_losses: int = 3

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.max_daily_loss_pct, "max_daily_loss_pct"),
            (self.max_weekly_loss_pct, "max_weekly_loss_pct"),
            (self.max_drawdown_pct, "max_drawdown_pct"),
        ):
            if not Decimal("0") <= value <= Decimal("1"):
                raise ValueError(f"{field_name} must be between 0 and 1")
        if self.max_spread_bps < Decimal("0"):
            raise ValueError("max_spread_bps cannot be negative")
        if self.max_consecutive_losses < 0:
            raise ValueError("max_consecutive_losses cannot be negative")


@dataclass(frozen=True, slots=True)
class AutomationHealthSnapshot:
    """Inputs used to decide whether automation must stop."""

    daily_pnl_pct: Decimal = Decimal("0")
    weekly_pnl_pct: Decimal = Decimal("0")
    drawdown_pct: Decimal = Decimal("0")
    consecutive_losses: int = 0
    volatility_shock: bool = False
    stale_data: bool = False
    exchange_outage: bool = False
    abnormal_spread_bps: Decimal = Decimal("0")
    model_error: bool = False
    risk_error: bool = False
    operator_present: bool = True

    def __post_init__(self) -> None:
        if self.consecutive_losses < 0:
            raise ValueError("consecutive_losses cannot be negative")
        if self.abnormal_spread_bps < Decimal("0"):
            raise ValueError("abnormal_spread_bps cannot be negative")


@dataclass(frozen=True, slots=True)
class CircuitBreakerDecision:
    """Circuit breaker decision for one automation check."""

    stop_required: bool
    reasons: tuple[str, ...]

    def require_running_allowed(self) -> None:
        if self.stop_required:
            raise RuntimeError("; ".join(self.reasons))


def evaluate_circuit_breakers(
    snapshot: AutomationHealthSnapshot,
    *,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreakerDecision:
    """Return all active stop reasons for the current automation health."""

    active_config = config or CircuitBreakerConfig()
    reasons: list[str] = []
    if snapshot.daily_pnl_pct <= -active_config.max_daily_loss_pct:
        reasons.append("daily loss limit breached")
    if snapshot.weekly_pnl_pct <= -active_config.max_weekly_loss_pct:
        reasons.append("weekly loss limit breached")
    if snapshot.drawdown_pct >= active_config.max_drawdown_pct:
        reasons.append("max drawdown breached")
    if snapshot.stale_data:
        reasons.append("stale data")
    if snapshot.exchange_outage:
        reasons.append("exchange outage")
    if snapshot.abnormal_spread_bps > active_config.max_spread_bps:
        reasons.append("abnormal spread")
    if snapshot.consecutive_losses >= active_config.max_consecutive_losses > 0:
        reasons.append("consecutive loss limit breached")
    if snapshot.volatility_shock:
        reasons.append("volatility shock")
    if snapshot.model_error:
        reasons.append("model error")
    if snapshot.risk_error:
        reasons.append("risk error")
    if not snapshot.operator_present:
        reasons.append("operator presence required")
    return CircuitBreakerDecision(stop_required=bool(reasons), reasons=tuple(reasons))
