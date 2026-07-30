from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from abtp.domain import (
    Asset,
    AssetPair,
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskCheck,
    RiskDecision,
    RiskDecisionStatus,
    Signal,
    SignalDirection,
)
from abtp.exchanges import ExchangeMode, UnavailableExchangeError, UnsafeLiveOperationError
from abtp.execution import (
    OrderRouteMode,
    OrderRouterConfig,
    PaperOrderRouter,
    PaperSafeExecutionEngine,
)
from abtp.repositories import AuditRepository, OrderRepository

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_execution_is_idempotent_and_records_lifecycle_and_audit(
    migrated_connection,
) -> None:
    orders = OrderRepository(migrated_connection)
    audits = AuditRepository(migrated_connection)
    engine = PaperSafeExecutionEngine(
        router=PaperOrderRouter(),
        order_repository=orders,
        audit_repository=audits,
    )
    intent = _approved_intent()

    first = engine.submit(
        intent,
        idempotency_key="idem-1",
        submitted_at=NOW,
        execution_price=Decimal("100"),
    )
    second = engine.submit(
        intent,
        idempotency_key="idem-1",
        submitted_at=NOW,
        execution_price=Decimal("100"),
    )

    lifecycle = orders.list_lifecycle_events(str(intent.id))
    audit_events = audits.list_by_correlation(str(intent.id))
    assert first is second
    assert first.accepted
    assert first.status is OrderStatus.FILLED
    assert first.fill_summary is not None
    assert first.fill_summary.is_complete
    assert tuple(event.status for event in lifecycle) == (
        OrderStatus.SUBMITTED,
        OrderStatus.FILLED,
    )
    assert len(audit_events) == 1
    assert audit_events[0].payload["idempotency_key"] == "idem-1"


def test_unapproved_order_intent_is_rejected_before_routing() -> None:
    engine = PaperSafeExecutionEngine(router=PaperOrderRouter())
    intent = _intent_without_risk()

    result = engine.submit(
        intent,
        idempotency_key="blocked",
        submitted_at=NOW,
        execution_price=Decimal("100"),
    )

    assert not result.accepted
    assert result.status is OrderStatus.RISK_REJECTED
    assert result.route_result is None
    assert "cannot bypass risk decision" in str(result.reason)


def test_partial_paper_fill_remains_submitted() -> None:
    engine = PaperSafeExecutionEngine(
        router=PaperOrderRouter(config=OrderRouterConfig(fill_ratio=Decimal("0.5")))
    )

    result = engine.submit(
        _approved_intent(quantity=Decimal("0.02")),
        idempotency_key="partial",
        submitted_at=NOW,
        execution_price=Decimal("100"),
    )

    assert result.accepted
    assert result.status is OrderStatus.SUBMITTED
    assert result.fill_summary is not None
    assert result.fill_summary.filled_quantity == Decimal("0.010")
    assert result.fill_summary.is_partial
    assert result.reason == "partial paper fill"


def test_adapter_failure_is_recorded_as_failed_route() -> None:
    engine = PaperSafeExecutionEngine(router=PaperOrderRouter(adapter=_FailingAdapter()))

    result = engine.submit(
        _approved_intent(),
        idempotency_key="adapter-fail",
        submitted_at=NOW,
        execution_price=Decimal("100"),
    )

    assert not result.accepted
    assert result.status is OrderStatus.FAILED
    assert result.route_result is not None
    assert result.route_result.reason == "fixture adapter unavailable"


def test_live_route_is_impossible_in_stage_024() -> None:
    with pytest.raises(UnsafeLiveOperationError, match="live order route"):
        OrderRouterConfig(mode=OrderRouteMode.LIVE)
    with pytest.raises(UnsafeLiveOperationError, match="live adapters"):
        PaperOrderRouter(adapter=_LiveLikeAdapter())


def _approved_intent(quantity: Decimal = Decimal("0.01")) -> OrderIntent:
    order_id = UUID("00000000-0000-0000-0000-000000000024")
    signal = _signal()
    decision = RiskDecision(
        order_intent_id=order_id,
        status=RiskDecisionStatus.APPROVED,
        checks=(RiskCheck("fixture-risk", True, "risk approved"),),
        evaluated_at=NOW,
        policy_version="stage-022.fixture",
        rationale="fixture approved",
        max_position_size=Decimal("1"),
        stop_loss_required=True,
        kill_switch_active=False,
    )
    return OrderIntent(
        id=order_id,
        pair=signal.pair,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=quantity,
        created_at=NOW,
        signal=signal,
        risk_decision=decision,
        status=OrderStatus.RISK_APPROVED,
        client_order_ref="client-ref-024",
    )


def _intent_without_risk() -> OrderIntent:
    signal = _signal()
    return OrderIntent(
        pair=signal.pair,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        created_at=NOW,
        signal=signal,
    )


def _signal() -> Signal:
    return Signal(
        source="fixture-strategy",
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        generated_at=NOW,
        direction=SignalDirection.BUY,
        confidence=Decimal("0.50"),
        inputs_ref="fixture:features:1",
        rationale="fixture signal",
    )


class _FailingAdapter:
    @property
    def name(self) -> str:
        return "failing"

    @property
    def mode(self) -> ExchangeMode:
        return ExchangeMode.SANDBOX

    def submit_order(self, intent: OrderIntent) -> object:
        raise UnavailableExchangeError("fixture adapter unavailable")


class _LiveLikeAdapter(_FailingAdapter):
    @property
    def mode(self) -> ExchangeMode:
        return ExchangeMode.LIVE
