from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.automation import (
    AutomationController,
    AutomationEvidence,
    AutomationHealthSnapshot,
    AutomationMode,
    AutomationPolicy,
)
from abtp.domain import (
    Asset,
    AssetPair,
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    Signal,
    SignalDirection,
)
from abtp.exchanges import ExchangeMode, ExchangeOrder, RateLimitState
from abtp.live import SupervisedLiveGatewayConfig, SupervisedLiveTradingGateway
from abtp.security import AuthenticatedPrincipal, SecurityRole

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_automation_cannot_enable_until_evidence_gates_pass() -> None:
    controller = _controller()
    decision = controller.enable(
        principal=_risk_manager(),
        evidence=_evidence(paper_trading_eligible=False),
        updated_at=NOW,
    )

    assert not decision.allowed
    assert decision.mode is AutomationMode.DISABLED
    assert "paper-trading eligibility gate has not passed" in decision.reasons
    with pytest.raises(RuntimeError, match="paper-trading eligibility"):
        controller.require_can_automate()


def test_automation_enables_with_reviewed_evidence_and_required_role() -> None:
    controller = _controller()

    decision = controller.enable(
        principal=_risk_manager(),
        evidence=_evidence(),
        updated_at=NOW,
    )

    assert decision.allowed
    assert decision.mode is AutomationMode.ENABLED
    controller.require_can_automate()


def test_viewer_cannot_enable_or_pause_automation() -> None:
    controller = _controller()
    viewer = AuthenticatedPrincipal("viewer", frozenset({SecurityRole.VIEWER}))

    with pytest.raises(PermissionError, match="manage_risk"):
        controller.enable(principal=viewer, evidence=_evidence(), updated_at=NOW)
    with pytest.raises(PermissionError, match="control_paper"):
        controller.pause(principal=viewer, reason="pause", updated_at=NOW)


def test_pause_resume_and_kill_switch_controls() -> None:
    controller = _controller()
    principal = _risk_manager()

    controller.enable(principal=principal, evidence=_evidence(), updated_at=NOW)
    pause = controller.pause(principal=principal, reason="operator pause", updated_at=NOW)
    resume = controller.resume(
        principal=principal,
        evidence=_evidence(),
        updated_at=NOW + timedelta(minutes=1),
    )
    kill = controller.activate_kill_switch(
        principal=principal,
        reason="manual shutdown",
        updated_at=NOW + timedelta(minutes=2),
    )
    blocked_resume = controller.resume(
        principal=principal,
        evidence=_evidence(),
        updated_at=NOW + timedelta(minutes=3),
    )

    assert pause.mode is AutomationMode.PAUSED
    assert resume.mode is AutomationMode.ENABLED
    assert kill.mode is AutomationMode.KILL_SWITCH
    assert blocked_resume.mode is AutomationMode.KILL_SWITCH
    assert blocked_resume.reasons == ("kill switch is active",)


def test_health_evaluation_trips_kill_switch_immediately() -> None:
    controller = _controller()
    controller.enable(principal=_risk_manager(), evidence=_evidence(), updated_at=NOW)

    decision = controller.evaluate_health(
        AutomationHealthSnapshot(stale_data=True),
        checked_at=NOW + timedelta(minutes=1),
    )

    assert not decision.allowed
    assert decision.mode is AutomationMode.KILL_SWITCH
    assert decision.reasons == ("stale data",)
    with pytest.raises(RuntimeError, match="stale data"):
        controller.require_can_automate()


def test_positive_live_pnl_policy_blocks_when_required() -> None:
    controller = _controller(policy=AutomationPolicy(require_positive_live_pnl=True))

    decision = controller.enable(
        principal=_risk_manager(),
        evidence=_evidence(live_pnl_pct=Decimal("0")),
        updated_at=NOW,
    )

    assert not decision.allowed
    assert "positive live P/L evidence is required" in decision.reasons


def _controller(policy: AutomationPolicy | None = None) -> AutomationController:
    gateway = SupervisedLiveTradingGateway(
        adapter=FakeAdapter(),
        config=SupervisedLiveGatewayConfig(
            enable_supervised_live=True,
            runtime_live_execution_supported=True,
        ),
    )
    return AutomationController(gateway=gateway, policy=policy)


def _risk_manager() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal("risk-manager", frozenset({SecurityRole.RISK_MANAGER}))


def _evidence(
    *,
    paper_trading_eligible: bool = True,
    live_pnl_pct: Decimal = Decimal("0"),
) -> AutomationEvidence:
    return AutomationEvidence(
        paper_trading_eligible=paper_trading_eligible,
        small_live_manually_reviewed=True,
        live_pnl_pct=live_pnl_pct,
        drawdown_pct=Decimal("0.01"),
        consecutive_losses=0,
        volatility_shock=False,
        exchange_healthy=True,
        operator_present=True,
    )


class FakeAdapter:
    @property
    def name(self) -> str:
        return "fake-live"

    @property
    def mode(self) -> ExchangeMode:
        return ExchangeMode.LIVE

    def submit_order(self, intent: OrderIntent) -> ExchangeOrder:
        return ExchangeOrder(
            exchange_order_id="unused",
            intent=intent,
            status=OrderStatus.FILLED,
            submitted_at=NOW,
        )

    def rate_limit_state(self) -> RateLimitState:
        return RateLimitState(limit=1, remaining=1, reset_at=NOW)

    def symbols(self) -> tuple[object, ...]:
        return ()

    def balances(self) -> tuple[object, ...]:
        return ()

    def ticker(self, pair: AssetPair) -> object:
        return object()

    def candles(self, pair: AssetPair, interval: str, limit: int) -> tuple[object, ...]:
        return ()

    def order_book(self, pair: AssetPair) -> object:
        return object()

    def get_order(self, exchange_order_id: str) -> ExchangeOrder:
        return self.submit_order(
            OrderIntent(
                pair=AssetPair(Asset("BTC"), Asset("USDT")),
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("0.0001"),
                created_at=NOW,
                signal=Signal(
                    source="fixture",
                    pair=AssetPair(Asset("BTC"), Asset("USDT")),
                    generated_at=NOW,
                    direction=SignalDirection.BUY,
                    confidence=Decimal("0.75"),
                    inputs_ref="fixture",
                    rationale="fixture",
                ),
            )
        )

    def cancel_order(self, exchange_order_id: str) -> ExchangeOrder:
        return self.get_order(exchange_order_id)
