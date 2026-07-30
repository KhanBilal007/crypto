from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.domain import (
    Asset,
    AssetPair,
    OrderIntent,
    OrderSide,
    OrderType,
    RiskCheck,
    RiskDecision,
    RiskDecisionStatus,
    Signal,
    SignalDirection,
)
from abtp.live import LIVE_APPROVAL_CONFIRMATION, LiveApprovalToken, validate_live_approval

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_live_approval_must_match_order_and_phrase() -> None:
    intent = _approved_intent()
    token = LiveApprovalToken.create(
        order_intent_id=intent.id,
        approved_by="operator",
        approved_at=NOW,
        max_quantity=Decimal("0.001"),
        max_notional=Decimal("25"),
        confirmation_phrase="WRONG",
    )

    result = validate_live_approval(
        intent,
        token,
        now=NOW,
        estimated_notional=Decimal("10"),
    )

    assert not result.allowed
    assert "approval confirmation phrase is invalid" in result.reasons


def test_live_approval_rejects_expired_or_oversized_orders() -> None:
    intent = _approved_intent(quantity=Decimal("0.0002"))
    token = LiveApprovalToken.create(
        order_intent_id=intent.id,
        approved_by="operator",
        approved_at=NOW,
        max_quantity=Decimal("0.0001"),
        max_notional=Decimal("5"),
        confirmation_phrase=LIVE_APPROVAL_CONFIRMATION,
    )

    result = validate_live_approval(
        intent,
        token,
        now=NOW + timedelta(minutes=6),
        estimated_notional=Decimal("20"),
    )

    assert not result.allowed
    assert "approval token is expired" in result.reasons
    assert "order quantity exceeds approved maximum" in result.reasons
    assert "order notional exceeds approved maximum" in result.reasons


def _approved_intent(quantity: Decimal = Decimal("0.0001")) -> OrderIntent:
    initial = OrderIntent(
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=quantity,
        created_at=NOW,
        signal=Signal(
            source="fixture",
            pair=AssetPair(Asset("BTC"), Asset("USDT")),
            generated_at=NOW,
            direction=SignalDirection.BUY,
            confidence=Decimal("0.75"),
            inputs_ref="fixture:features",
            rationale="fixture",
        ),
    )
    decision = RiskDecision(
        order_intent_id=initial.id,
        status=RiskDecisionStatus.APPROVED,
        checks=(RiskCheck("fixture", True, "approved"),),
        evaluated_at=NOW,
        policy_version="risk-v1",
        rationale="approved",
        max_position_size=Decimal("0.001"),
    )
    return OrderIntent(
        id=initial.id,
        pair=initial.pair,
        side=initial.side,
        order_type=initial.order_type,
        quantity=initial.quantity,
        created_at=initial.created_at,
        signal=initial.signal,
        risk_decision=decision,
    )
