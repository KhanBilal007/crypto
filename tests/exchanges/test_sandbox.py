from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
from abtp.exchanges import (
    ExchangeAdapter,
    ExchangeMode,
    InvalidSymbolError,
    OrderRejectedError,
    RateLimitExceededError,
    SandboxExchangeAdapter,
    StaleDataError,
    UnsafeLiveOperationError,
    UnsupportedOperationError,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def pair() -> AssetPair:
    return AssetPair(Asset("BTC"), Asset("USDT"))


def signal() -> Signal:
    return Signal(
        source="fixture-strategy",
        pair=pair(),
        generated_at=NOW,
        direction=SignalDirection.BUY,
        confidence=Decimal("0.75"),
        inputs_ref="fixture:prediction:1",
        rationale="Fixture signal.",
    )


def approved_intent(
    *,
    side: OrderSide = OrderSide.BUY,
    quantity: Decimal = Decimal("0.001"),
    created_at: datetime = NOW,
    limit_price: Decimal | None = None,
) -> OrderIntent:
    initial = OrderIntent(
        pair=pair(),
        side=side,
        order_type=OrderType.LIMIT if limit_price is not None else OrderType.MARKET,
        quantity=quantity,
        created_at=created_at,
        signal=signal(),
        limit_price=limit_price,
    )
    decision = RiskDecision(
        order_intent_id=initial.id,
        status=RiskDecisionStatus.APPROVED,
        checks=(RiskCheck("fixture", True, "approved"),),
        evaluated_at=created_at,
        policy_version="risk-v1",
        rationale="Approved fixture order.",
        max_position_size=Decimal("1"),
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
        limit_price=initial.limit_price,
    )


def rejected_intent() -> OrderIntent:
    initial = OrderIntent(
        pair=pair(),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.001"),
        created_at=NOW,
        signal=signal(),
    )
    decision = RiskDecision(
        order_intent_id=initial.id,
        status=RiskDecisionStatus.REJECTED,
        checks=(RiskCheck("fixture", False, "rejected"),),
        evaluated_at=NOW,
        policy_version="risk-v1",
        rationale="Rejected fixture order.",
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


def test_sandbox_satisfies_exchange_adapter_contract() -> None:
    adapter: ExchangeAdapter = SandboxExchangeAdapter(now=NOW)

    assert adapter.name == "sandbox"
    assert adapter.mode is ExchangeMode.SANDBOX
    assert adapter.symbols()[0].pair.symbol == "BTC/USDT"
    assert adapter.balances()[0].asset.symbol == "BTC"
    assert adapter.ticker(pair()).price == Decimal("100000")
    assert adapter.candles(pair(), "1m", 2)[0].interval == "1m"
    assert adapter.order_book(pair()).pair == pair()


def test_sandbox_order_lifecycle_requires_risk_approved_intent() -> None:
    adapter = SandboxExchangeAdapter(now=NOW)
    intent = approved_intent()

    order = adapter.submit_order(intent)

    assert order.status is OrderStatus.FILLED
    assert order.filled_quantity == Decimal("0.001")
    assert order.average_fill_price == Decimal("100000")
    assert adapter.get_order(order.exchange_order_id) == order


def test_sandbox_rejects_missing_or_rejected_risk_decision() -> None:
    adapter = SandboxExchangeAdapter(now=NOW)
    no_decision = OrderIntent(
        pair=pair(),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.001"),
        created_at=NOW,
        signal=signal(),
    )

    with pytest.raises(OrderRejectedError, match="risk-approved"):
        adapter.submit_order(no_decision)
    with pytest.raises(OrderRejectedError, match="rejected"):
        adapter.submit_order(rejected_intent())


def test_sandbox_rejects_mismatched_risk_decision() -> None:
    intent = approved_intent()
    wrong_decision = RiskDecision(
        order_intent_id=UUID("00000000-0000-0000-0000-000000000009"),
        status=RiskDecisionStatus.APPROVED,
        checks=(RiskCheck("fixture", True, "approved"),),
        evaluated_at=NOW,
        policy_version="risk-v1",
        rationale="Approved wrong order.",
    )
    with pytest.raises(ValueError, match="risk decision must reference this order intent"):
        OrderIntent(
            id=intent.id,
            pair=intent.pair,
            side=intent.side,
            order_type=intent.order_type,
            quantity=intent.quantity,
            created_at=intent.created_at,
            signal=intent.signal,
            risk_decision=wrong_decision,
        )


def test_sandbox_rate_limit_behavior() -> None:
    adapter = SandboxExchangeAdapter(now=NOW, rate_limit=1)

    assert adapter.ticker(pair()).price == Decimal("100000")
    assert adapter.rate_limit_state().remaining == 0
    with pytest.raises(RateLimitExceededError):
        adapter.balances()


def test_sandbox_rejects_invalid_symbol_and_stale_order() -> None:
    adapter = SandboxExchangeAdapter(now=NOW)
    invalid_pair = AssetPair(Asset("ETH"), Asset("USDT"))

    with pytest.raises(InvalidSymbolError):
        adapter.ticker(invalid_pair)
    with pytest.raises(StaleDataError):
        adapter.submit_order(approved_intent(created_at=NOW - timedelta(minutes=6)))


def test_sandbox_rejects_lot_tick_and_balance_errors() -> None:
    adapter = SandboxExchangeAdapter(now=NOW)

    with pytest.raises(OrderRejectedError, match="lot_size"):
        adapter.submit_order(approved_intent(quantity=Decimal("0.00015")))
    with pytest.raises(OrderRejectedError, match="tick_size"):
        adapter.submit_order(approved_intent(limit_price=Decimal("100000.001")))
    with pytest.raises(OrderRejectedError, match="insufficient base balance"):
        adapter.submit_order(approved_intent(side=OrderSide.SELL, quantity=Decimal("2")))


def test_sandbox_blocks_live_credentials_live_mode_and_unsupported_operations() -> None:
    with pytest.raises(UnsafeLiveOperationError):
        SandboxExchangeAdapter(now=NOW, mode=ExchangeMode.LIVE)
    with pytest.raises(UnsafeLiveOperationError):
        SandboxExchangeAdapter(now=NOW, live_credentials_present=True)

    adapter = SandboxExchangeAdapter(now=NOW)
    with pytest.raises(UnsupportedOperationError, match="withdrawals"):
        adapter.withdraw(Asset("BTC"), Decimal("0.1"))
    with pytest.raises(UnsupportedOperationError, match="margin"):
        adapter.enable_margin()
