"""Limited automation controller with evidence gates and immediate shutdown."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.automation.circuit_breakers import (
    AutomationHealthSnapshot,
    CircuitBreakerConfig,
    CircuitBreakerDecision,
    evaluate_circuit_breakers,
)
from abtp.data import normalize_timestamp
from abtp.live import SupervisedLiveTradingGateway
from abtp.notifications import NotificationAlert, NotificationService
from abtp.security import AuthenticatedPrincipal, SecurityPermission


class AutomationMode(StrEnum):
    """Limited automation state."""

    DISABLED = "disabled"
    ENABLED = "enabled"
    PAUSED = "paused"
    KILL_SWITCH = "kill_switch"


@dataclass(frozen=True, slots=True)
class AutomationEvidence:
    """Evidence gates required before automation can be enabled."""

    paper_trading_eligible: bool
    small_live_manually_reviewed: bool
    live_pnl_pct: Decimal
    drawdown_pct: Decimal
    consecutive_losses: int
    volatility_shock: bool
    exchange_healthy: bool
    operator_present: bool

    def __post_init__(self) -> None:
        if self.consecutive_losses < 0:
            raise ValueError("consecutive_losses cannot be negative")
        if self.drawdown_pct < Decimal("0"):
            raise ValueError("drawdown_pct cannot be negative")


@dataclass(frozen=True, slots=True)
class AutomationPolicy:
    """Automation eligibility policy."""

    max_drawdown_pct: Decimal = Decimal("0.05")
    max_consecutive_losses: int = 1
    require_positive_live_pnl: bool = False

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.max_drawdown_pct <= Decimal("1"):
            raise ValueError("max_drawdown_pct must be between 0 and 1")
        if self.max_consecutive_losses < 0:
            raise ValueError("max_consecutive_losses cannot be negative")


@dataclass(frozen=True, slots=True)
class AutomationControlState:
    """Operator control state for limited automation."""

    mode: AutomationMode = AutomationMode.DISABLED
    reason: str = "automation initialized disabled"
    updated_at: datetime = datetime(2026, 1, 1)
    updated_by: str = "system"

    def __post_init__(self) -> None:
        object.__setattr__(self, "updated_at", normalize_timestamp(self.updated_at))
        if not self.reason.strip():
            raise ValueError("automation control reason is required")
        if not self.updated_by.strip():
            raise ValueError("updated_by is required")

    @property
    def automation_allowed(self) -> bool:
        return self.mode is AutomationMode.ENABLED


@dataclass(frozen=True, slots=True)
class AutomationDecision:
    """Result of an automation state transition or health check."""

    mode: AutomationMode
    allowed: bool
    reasons: tuple[str, ...]
    circuit_breaker: CircuitBreakerDecision | None = None
    alert: NotificationAlert | None = None


class AutomationController:
    """Enable limited automation only after evidence gates pass."""

    def __init__(
        self,
        *,
        gateway: SupervisedLiveTradingGateway,
        policy: AutomationPolicy | None = None,
        circuit_breakers: CircuitBreakerConfig | None = None,
        notifications: NotificationService | None = None,
        state: AutomationControlState | None = None,
    ) -> None:
        self._gateway = gateway
        self._policy = policy or AutomationPolicy()
        self._circuit_breakers = circuit_breakers or CircuitBreakerConfig()
        self._notifications = notifications
        self._state = state or AutomationControlState()

    @property
    def state(self) -> AutomationControlState:
        return self._state

    @property
    def gateway(self) -> SupervisedLiveTradingGateway:
        return self._gateway

    def enable(
        self,
        *,
        principal: AuthenticatedPrincipal,
        evidence: AutomationEvidence,
        updated_at: datetime,
    ) -> AutomationDecision:
        """Enable automation only when authorization and evidence gates pass."""

        principal.require(SecurityPermission.MANAGE_RISK)
        reasons = _evidence_reasons(evidence, self._policy)
        if reasons:
            self._state = replace(
                self._state,
                mode=AutomationMode.DISABLED,
                reason="; ".join(reasons),
                updated_at=updated_at,
                updated_by=principal.principal_id,
            )
            return AutomationDecision(AutomationMode.DISABLED, False, reasons)
        self._state = AutomationControlState(
            mode=AutomationMode.ENABLED,
            reason="automation evidence gates passed",
            updated_at=updated_at,
            updated_by=principal.principal_id,
        )
        return AutomationDecision(AutomationMode.ENABLED, True, ())

    def pause(
        self,
        *,
        principal: AuthenticatedPrincipal,
        reason: str,
        updated_at: datetime,
    ) -> AutomationDecision:
        """Pause automation immediately."""

        principal.require(SecurityPermission.CONTROL_PAPER)
        self._state = AutomationControlState(
            mode=AutomationMode.PAUSED,
            reason=reason,
            updated_at=updated_at,
            updated_by=principal.principal_id,
        )
        return AutomationDecision(AutomationMode.PAUSED, False, (reason,))

    def resume(
        self,
        *,
        principal: AuthenticatedPrincipal,
        evidence: AutomationEvidence,
        updated_at: datetime,
    ) -> AutomationDecision:
        """Resume only through the same evidence gates as enable."""

        if self._state.mode is AutomationMode.KILL_SWITCH:
            return AutomationDecision(
                AutomationMode.KILL_SWITCH,
                False,
                ("kill switch is active",),
            )
        return self.enable(principal=principal, evidence=evidence, updated_at=updated_at)

    def activate_kill_switch(
        self,
        *,
        principal: AuthenticatedPrincipal,
        reason: str,
        updated_at: datetime,
    ) -> AutomationDecision:
        """Stop automation instantly and keep it stopped."""

        principal.require(SecurityPermission.CONTROL_PAPER)
        self._state = AutomationControlState(
            mode=AutomationMode.KILL_SWITCH,
            reason=reason,
            updated_at=updated_at,
            updated_by=principal.principal_id,
        )
        return AutomationDecision(AutomationMode.KILL_SWITCH, False, (reason,))

    def evaluate_health(
        self,
        snapshot: AutomationHealthSnapshot,
        *,
        checked_at: datetime,
    ) -> AutomationDecision:
        """Evaluate circuit breakers and stop automation if any breaker trips."""

        decision = evaluate_circuit_breakers(snapshot, config=self._circuit_breakers)
        if not decision.stop_required and self._state.automation_allowed:
            return AutomationDecision(
                self._state.mode,
                True,
                (),
                circuit_breaker=decision,
            )
        if decision.stop_required:
            reason = "; ".join(decision.reasons)
            self._state = AutomationControlState(
                mode=AutomationMode.KILL_SWITCH,
                reason=reason,
                updated_at=checked_at,
                updated_by="circuit_breaker",
            )
            alert = self._dispatch_alert(reason=reason, checked_at=checked_at)
            return AutomationDecision(
                AutomationMode.KILL_SWITCH,
                False,
                decision.reasons,
                circuit_breaker=decision,
                alert=alert,
            )
        return AutomationDecision(self._state.mode, False, (self._state.reason,))

    def require_can_automate(self) -> None:
        """Fail closed before any future automated gateway submission."""

        if not self._state.automation_allowed:
            raise RuntimeError(self._state.reason)

    def _dispatch_alert(self, *, reason: str, checked_at: datetime) -> NotificationAlert | None:
        if self._notifications is None:
            return None
        alert = self._notifications.risk_halt_alert(reason=reason, occurred_at=checked_at)
        self._notifications.dispatch(alert, sent_at=checked_at, live_mode_event=True)
        return alert


def _evidence_reasons(
    evidence: AutomationEvidence,
    policy: AutomationPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not evidence.paper_trading_eligible:
        reasons.append("paper-trading eligibility gate has not passed")
    if not evidence.small_live_manually_reviewed:
        reasons.append("small-live results have not been manually reviewed")
    if policy.require_positive_live_pnl and evidence.live_pnl_pct <= Decimal("0"):
        reasons.append("positive live P/L evidence is required")
    if evidence.drawdown_pct > policy.max_drawdown_pct:
        reasons.append("drawdown evidence exceeds automation limit")
    if evidence.consecutive_losses > policy.max_consecutive_losses:
        reasons.append("consecutive loss evidence exceeds automation limit")
    if evidence.volatility_shock:
        reasons.append("volatility shock blocks automation")
    if not evidence.exchange_healthy:
        reasons.append("exchange health blocks automation")
    if not evidence.operator_present:
        reasons.append("operator presence is required")
    return tuple(reasons)
