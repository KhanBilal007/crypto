"""Framework-neutral paper trading API contracts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from abtp.paper.account import PaperTrade
from abtp.paper.engine import PaperTradingCycleResult, PaperTradingEngine


class PaperAPIRole(StrEnum):
    """Paper API authorization roles."""

    READ = "paper:read"
    CONTROL = "paper:control"


class PaperAPIError(ValueError):
    """Base paper API error."""


class PaperPermissionError(PaperAPIError):
    """Raised when a caller lacks the required paper API role."""


class UnsafePaperActionError(PaperAPIError):
    """Raised for actions outside the Stage 028 safe-control surface."""


@dataclass(frozen=True, slots=True)
class PaperAPIRequestContext:
    """Authenticated caller context without storing secret values."""

    principal: str
    roles: frozenset[PaperAPIRole]

    def __post_init__(self) -> None:
        if not self.principal.strip():
            raise ValueError("principal is required")

    def require(self, role: PaperAPIRole) -> None:
        if role not in self.roles:
            raise PaperPermissionError(f"missing required role: {role.value}")


@dataclass(frozen=True, slots=True)
class PaperControlState:
    """Safe operator controls exposed by Stage 028."""

    paused: bool = False
    kill_switch_active: bool = False
    reason: str = "paper trading controls initialized"
    updated_at: datetime = datetime(2026, 1, 1, tzinfo=UTC)
    updated_by: str = "system"

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("control reason is required")
        if not self.updated_by.strip():
            raise ValueError("updated_by is required")


@dataclass(frozen=True, slots=True)
class PaperPortfolioStatus:
    """API-safe paper account snapshot."""

    cash: Decimal
    base_quantity: Decimal
    average_entry_price: Decimal
    realized_pnl: Decimal
    fees_paid: Decimal
    equity: Decimal
    drawdown_pct: Decimal

    def as_dict(self) -> dict[str, str]:
        return {
            "cash": str(self.cash),
            "base_quantity": str(self.base_quantity),
            "average_entry_price": str(self.average_entry_price),
            "realized_pnl": str(self.realized_pnl),
            "fees_paid": str(self.fees_paid),
            "equity": str(self.equity),
            "drawdown_pct": str(self.drawdown_pct),
        }


@dataclass(frozen=True, slots=True)
class PaperParameterHealth:
    """Parameter health row visible to the paper dashboard."""

    key: str
    value: str
    status: str
    reason: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.key, "parameter key"),
            (self.status, "parameter status"),
            (self.reason, "parameter reason"),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")

    def as_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "value": self.value,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class PaperStatusResponse:
    """Read-only operator view of paper trading state."""

    current_btc_price: Decimal | None
    active_regime: str
    latest_signal: str
    latest_risk_decision: str
    blocked_reason: str
    data_health: str
    portfolio: PaperPortfolioStatus
    parameter_health: tuple[PaperParameterHealth, ...]
    paused: bool
    kill_switch_active: bool
    cycles_count: int
    trades_count: int
    updated_at: datetime

    def as_dict(self) -> dict[str, object]:
        return {
            "current_btc_price": str(self.current_btc_price) if self.current_btc_price else None,
            "active_regime": self.active_regime,
            "latest_signal": self.latest_signal,
            "latest_risk_decision": self.latest_risk_decision,
            "blocked_reason": self.blocked_reason,
            "data_health": self.data_health,
            "portfolio": self.portfolio.as_dict(),
            "parameter_health": [item.as_dict() for item in self.parameter_health],
            "paused": self.paused,
            "kill_switch_active": self.kill_switch_active,
            "cycles_count": self.cycles_count,
            "trades_count": self.trades_count,
            "updated_at": self.updated_at.isoformat(),
        }


class PaperTradingAPI:
    """Dependency-free API facade for paper state and safe controls."""

    def __init__(
        self,
        engine: PaperTradingEngine,
        *,
        control_state: PaperControlState | None = None,
    ) -> None:
        self._engine = engine
        self._control_state = control_state or PaperControlState()

    @property
    def control_state(self) -> PaperControlState:
        return self._control_state

    def status(
        self,
        context: PaperAPIRequestContext,
        *,
        mark_price: Decimal | None = None,
    ) -> PaperStatusResponse:
        """Return a read-only paper status response."""

        context.require(PaperAPIRole.READ)
        latest = self._latest_cycle()
        price = mark_price or (latest.snapshot.candle.close if latest else Decimal("1"))
        account = self._engine.account
        return PaperStatusResponse(
            current_btc_price=latest.snapshot.candle.close if latest else None,
            active_regime=latest.regime.label.value if latest else "unknown",
            latest_signal=_latest_signal(latest),
            latest_risk_decision=(
                latest.risk_decision_status or "not_evaluated" if latest else "not_evaluated"
            ),
            blocked_reason=_blocked_reason(latest, self._control_state),
            data_health=latest.snapshot.health.status if latest else "unavailable",
            portfolio=PaperPortfolioStatus(
                cash=account.state.cash,
                base_quantity=account.state.base_quantity,
                average_entry_price=account.state.average_entry_price,
                realized_pnl=account.state.realized_pnl,
                fees_paid=account.state.fees_paid,
                equity=account.equity(price),
                drawdown_pct=account.current_drawdown_pct(price),
            ),
            parameter_health=_parameter_health(latest),
            paused=self._control_state.paused,
            kill_switch_active=self._control_state.kill_switch_active,
            cycles_count=len(self._engine.cycles),
            trades_count=len(account.trades),
            updated_at=_updated_at(latest, self._control_state),
        )

    def trades(self, context: PaperAPIRequestContext) -> tuple[PaperTrade, ...]:
        """Return simulated paper trades only."""

        context.require(PaperAPIRole.READ)
        return self._engine.account.trades

    def cycles(self, context: PaperAPIRequestContext) -> tuple[PaperTradingCycleResult, ...]:
        """Return paper decision cycles for audit inspection."""

        context.require(PaperAPIRole.READ)
        return self._engine.cycles

    def pause(
        self,
        context: PaperAPIRequestContext,
        *,
        reason: str,
        updated_at: datetime,
    ) -> PaperControlState:
        """Pause paper trading from the operator control surface."""

        return self._update_control(
            context,
            paused=True,
            kill_switch_active=self._control_state.kill_switch_active,
            reason=reason,
            updated_at=updated_at,
        )

    def resume(
        self,
        context: PaperAPIRequestContext,
        *,
        reason: str,
        updated_at: datetime,
    ) -> PaperControlState:
        """Resume from pause without clearing an active kill switch."""

        return self._update_control(
            context,
            paused=False,
            kill_switch_active=self._control_state.kill_switch_active,
            reason=reason,
            updated_at=updated_at,
        )

    def activate_kill_switch(
        self,
        context: PaperAPIRequestContext,
        *,
        reason: str,
        updated_at: datetime,
    ) -> PaperControlState:
        """Activate the paper kill switch; Stage 028 does not expose clearing it."""

        return self._update_control(
            context,
            paused=True,
            kill_switch_active=True,
            reason=reason,
            updated_at=updated_at,
        )

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject order placement from the dashboard/API layer."""

        raise UnsafePaperActionError("Stage 028 API cannot submit orders")

    def _update_control(
        self,
        context: PaperAPIRequestContext,
        *,
        paused: bool,
        kill_switch_active: bool,
        reason: str,
        updated_at: datetime,
    ) -> PaperControlState:
        context.require(PaperAPIRole.CONTROL)
        if not reason.strip():
            raise ValueError("control reason is required")
        self._control_state = replace(
            self._control_state,
            paused=paused,
            kill_switch_active=kill_switch_active,
            reason=reason,
            updated_at=updated_at,
            updated_by=context.principal,
        )
        return self._control_state

    def _latest_cycle(self) -> PaperTradingCycleResult | None:
        cycles = self._engine.cycles
        return cycles[-1] if cycles else None


def _latest_signal(latest: PaperTradingCycleResult | None) -> str:
    if latest is None or latest.strategy_evaluation is None:
        return "not_evaluated"
    return latest.strategy_evaluation.signal.direction.value


def _blocked_reason(
    latest: PaperTradingCycleResult | None,
    control_state: PaperControlState,
) -> str:
    if control_state.kill_switch_active:
        return f"kill switch active: {control_state.reason}"
    if control_state.paused:
        return f"paper trading paused: {control_state.reason}"
    if latest is None:
        return "no paper cycle has run"
    if latest.skipped_reason:
        return latest.skipped_reason
    if latest.strategy_evaluation is not None and not latest.strategy_evaluation.is_trade_signal:
        return "; ".join(latest.strategy_evaluation.reasons)
    if latest.risk_decision_status == "rejected":
        return "risk engine rejected proposed paper order"
    if latest.execution_result is not None and latest.execution_result.reason:
        return latest.execution_result.reason
    return "not blocked"


def _parameter_health(
    latest: PaperTradingCycleResult | None,
) -> tuple[PaperParameterHealth, ...]:
    if latest is None:
        return ()
    values = latest.features.values
    quality = latest.features.quality
    status = quality.trust_level.value
    reason = ", ".join(quality.flags) if quality.flags else "trusted paper feature input"
    keys = (
        "market.close",
        "liquidity.spread_bps",
        "stream.latency_ms",
        "data_quality.flag_count",
    )
    return tuple(
        PaperParameterHealth(
            key=key,
            value=str(values.get(key, "")),
            status=status,
            reason=reason,
        )
        for key in keys
    )


def _updated_at(
    latest: PaperTradingCycleResult | None,
    control_state: PaperControlState,
) -> datetime:
    if latest is None:
        return control_state.updated_at
    return max(latest.snapshot.received_at, control_state.updated_at)
