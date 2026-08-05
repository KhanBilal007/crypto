from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.domain import (
    Asset,
    AssetPair,
    Candle,
    Exchange,
    OrderBookLevel,
    OrderBookSnapshot,
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
    Balance,
    ExchangeMode,
    ExchangeOrder,
    ExchangeSymbol,
    RateLimitState,
    Ticker,
)
from abtp.live import (
    LIVE_APPROVAL_CONFIRMATION,
    LiveApprovalToken,
    LiveMarketPreflight,
    SupervisedLiveGatewayConfig,
    SupervisedLiveTradingGateway,
)
from abtp.security import ExchangeKeyPermissions

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PAIR = AssetPair(Asset("BTC"), Asset("USDT"))


def test_gateway_lock_blocks_when_runtime_support_disabled() -> None:
    adapter = FakeLiveAdapter()
    gateway = SupervisedLiveTradingGateway(
        adapter=adapter,
        config=SupervisedLiveGatewayConfig(enable_supervised_live=True),
    )

    result = gateway.submit(
        _approved_intent(),
        approval=None,
        market=_market(),
        submitted_at=NOW,
    )

    assert not result.accepted
    assert result.reason == "runtime live execution support is disabled"
    assert adapter.submitted_intents == ()


def test_gateway_requires_manual_approval_before_adapter_submit() -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter)
    intent = _approved_intent()

    result = gateway.submit(intent, approval=None, market=_market(), submitted_at=NOW)

    assert not result.accepted
    assert "manual approval token is required" in result.reason
    assert adapter.submitted_intents == ()


def test_gateway_blocks_preflight_failure_before_adapter_submit() -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter)
    intent = _approved_intent(quantity=Decimal("0.001"))
    approval = _approval(intent, max_quantity=Decimal("0.001"), max_notional=Decimal("200"))

    result = gateway.submit(intent, approval=approval, market=_market(), submitted_at=NOW)

    assert not result.accepted
    assert "order notional exceeds tiny live risk limit" in result.reason
    assert adapter.submitted_intents == ()


def test_gateway_submits_only_after_risk_preflight_and_approval() -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter)
    intent = _approved_intent()

    result = gateway.submit(
        intent,
        approval=_approval(intent),
        market=_market(),
        submitted_at=NOW,
    )

    assert result.accepted
    assert result.trading_permitted
    assert result.status is OrderStatus.FILLED
    assert result.exchange_order is not None
    assert result.preflight is not None and result.preflight.allowed
    assert adapter.submitted_intents == (intent,)


def test_gateway_requires_live_mode_adapter() -> None:
    adapter = FakeLiveAdapter(mode=ExchangeMode.SANDBOX)
    gateway = SupervisedLiveTradingGateway(
        adapter=adapter,
        config=SupervisedLiveGatewayConfig(
            enable_supervised_live=True,
            runtime_live_execution_supported=True,
        ),
    )

    result = gateway.submit(
        _approved_intent(),
        approval=None,
        market=_market(),
        submitted_at=NOW,
    )

    assert not result.accepted
    assert result.reason == "live gateway requires a live-mode adapter"
    assert adapter.submitted_intents == ()


def _enabled_gateway(adapter: FakeLiveAdapter) -> SupervisedLiveTradingGateway:
    return SupervisedLiveTradingGateway(
        adapter=adapter,
        config=SupervisedLiveGatewayConfig(
            enable_supervised_live=True,
            runtime_live_execution_supported=True,
        ),
    )


def _approval(
    intent: OrderIntent,
    *,
    max_quantity: Decimal = Decimal("0.0001"),
    max_notional: Decimal = Decimal("25"),
) -> LiveApprovalToken:
    return LiveApprovalToken.create(
        order_intent_id=intent.id,
        approved_by="operator",
        approved_at=NOW,
        max_quantity=max_quantity,
        max_notional=max_notional,
        confirmation_phrase=LIVE_APPROVAL_CONFIRMATION,
    )


def _market() -> LiveMarketPreflight:
    return LiveMarketPreflight(
        price=Decimal("100000"),
        quote_balance_available=Decimal("1000"),
        account_equity=Decimal("10000"),
        fee_bps=Decimal("20"),
        spread_bps=Decimal("10"),
        slippage_bps=Decimal("5"),
        open_live_positions=0,
        permissions=ExchangeKeyPermissions.from_strings(
            exchange_name="fake-live",
            scopes=("read", "trade"),
            ip_allowlist=("203.0.113.10",),
        ),
        checked_at=NOW,
    )


def _approved_intent(quantity: Decimal = Decimal("0.0001")) -> OrderIntent:
    initial = OrderIntent(
        pair=PAIR,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=quantity,
        created_at=NOW,
        signal=Signal(
            source="fixture",
            pair=PAIR,
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


class FakeLiveAdapter:
    def __init__(self, *, mode: ExchangeMode = ExchangeMode.LIVE) -> None:
        self._mode = mode
        self._submitted: list[OrderIntent] = []

    @property
    def submitted_intents(self) -> tuple[OrderIntent, ...]:
        return tuple(self._submitted)

    @property
    def name(self) -> str:
        return "fake-live"

    @property
    def mode(self) -> ExchangeMode:
        return self._mode

    def symbols(self) -> tuple[ExchangeSymbol, ...]:
        return (
            ExchangeSymbol(
                pair=PAIR,
                tick_size=Decimal("0.01"),
                lot_size=Decimal("0.0001"),
                min_order_size=Decimal("0.0001"),
                maker_fee_bps=Decimal("10"),
                taker_fee_bps=Decimal("20"),
            ),
        )

    def balances(self) -> tuple[Balance, ...]:
        return (Balance(Asset("USDT"), Decimal("1000")),)

    def ticker(self, pair: AssetPair) -> Ticker:
        return Ticker(pair=pair, price=Decimal("100000"), captured_at=NOW, source_ref="fake")

    def candles(self, pair: AssetPair, interval: str, limit: int) -> tuple[Candle, ...]:
        opened_at = NOW - timedelta(minutes=1)
        return (
            Candle(
                exchange=Exchange("fake-live"),
                pair=pair,
                interval=interval,
                opened_at=opened_at,
                closed_at=NOW,
                open=Decimal("100000"),
                high=Decimal("100010"),
                low=Decimal("99990"),
                close=Decimal("100000"),
                volume=Decimal("1"),
            ),
        )

    def order_book(self, pair: AssetPair) -> OrderBookSnapshot:
        return OrderBookSnapshot(
            exchange=Exchange("fake-live"),
            pair=pair,
            captured_at=NOW,
            bids=(OrderBookLevel(Decimal("99999"), Decimal("1")),),
            asks=(OrderBookLevel(Decimal("100001"), Decimal("1")),),
            source_ref="fake:book",
        )

    def submit_order(self, intent: OrderIntent) -> ExchangeOrder:
        self._submitted.append(intent)
        return ExchangeOrder(
            exchange_order_id="fake-live-order-1",
            intent=intent,
            status=OrderStatus.FILLED,
            submitted_at=NOW,
            filled_quantity=intent.quantity,
            average_fill_price=Decimal("100000"),
            fee_paid=intent.quantity * Decimal("100000") * Decimal("20") / Decimal("10000"),
        )

    def get_order(self, exchange_order_id: str) -> ExchangeOrder:
        return replace(self.submit_order(_approved_intent()), exchange_order_id=exchange_order_id)

    def cancel_order(self, exchange_order_id: str) -> ExchangeOrder:
        return replace(self.get_order(exchange_order_id), status=OrderStatus.CANCELED)

    def rate_limit_state(self) -> RateLimitState:
        return RateLimitState(limit=100, remaining=99, reset_at=NOW + timedelta(minutes=1))
