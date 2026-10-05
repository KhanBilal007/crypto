from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from sqlite3 import OperationalError
from threading import Barrier

import pytest

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
    LivePreflightConfig,
    LiveSubmissionLedger,
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


def test_gateway_requires_manual_approval_before_adapter_submit(tmp_path: Path) -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    intent = _approved_intent()

    result = gateway.submit(intent, approval=None, market=_market(), submitted_at=NOW)

    assert not result.accepted
    assert "manual approval token is required" in result.reason
    assert adapter.submitted_intents == ()


def test_gateway_blocks_preflight_failure_before_adapter_submit(tmp_path: Path) -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    intent = _approved_intent(quantity=Decimal("0.001"))
    approval = _approval(intent, max_quantity=Decimal("0.001"), max_notional=Decimal("200"))

    result = gateway.submit(intent, approval=approval, market=_market(), submitted_at=NOW)

    assert not result.accepted
    assert "order notional exceeds tiny live risk limit" in result.reason
    assert adapter.submitted_intents == ()


def test_gateway_submits_only_after_risk_preflight_and_approval(tmp_path: Path) -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
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


def test_enabled_gateway_requires_persistent_ledger() -> None:
    adapter = FakeLiveAdapter()
    gateway = SupervisedLiveTradingGateway(
        adapter=adapter,
        config=SupervisedLiveGatewayConfig(
            enable_supervised_live=True,
            runtime_live_execution_supported=True,
        ),
        clock=lambda: NOW,
    )
    intent = _approved_intent()
    result = gateway.submit(intent, approval=_approval(intent), market=_market(), submitted_at=NOW)
    assert not result.accepted
    assert "persistent submission ledger is required" in result.reason
    assert not adapter.submitted_intents


@pytest.mark.parametrize("restart", [False, True])
@pytest.mark.parametrize("new_approval", [False, True])
def test_duplicate_intent_is_blocked_even_with_fresh_approval_after_restart(
    tmp_path: Path, restart: bool, new_approval: bool
) -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    intent = _approved_intent()
    approval = _approval(intent)
    assert gateway.submit(intent, approval=approval, market=_market(), submitted_at=NOW).accepted
    if restart:
        gateway = _enabled_gateway(adapter, tmp_path)
    second = gateway.submit(
        intent,
        approval=_approval(intent) if new_approval else approval,
        market=_market(),
        submitted_at=NOW,
    )
    assert not second.accepted
    assert "already been consumed" in second.reason
    assert adapter.submitted_intents == (intent,)


def test_approval_identifier_cannot_be_rebound_to_a_new_intent(tmp_path: Path) -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    intent = _approved_intent()
    approval = _approval(intent)
    assert gateway.submit(intent, approval=approval, market=_market(), submitted_at=NOW).accepted
    second_intent = _approved_intent()
    result = gateway.submit(
        second_intent,
        approval=replace(approval, order_intent_id=second_intent.id),
        market=_market(),
        submitted_at=NOW,
    )
    assert not result.accepted
    assert "already been consumed" in result.reason
    assert len(adapter.submitted_intents) == 1


def test_concurrent_gateway_instances_submit_the_intent_only_once(tmp_path: Path) -> None:
    adapter = FakeLiveAdapter()
    gateways = [_enabled_gateway(adapter, tmp_path), _enabled_gateway(adapter, tmp_path)]
    intent = _approved_intent()
    approval = _approval(intent)
    barrier = Barrier(2)

    def submit(gateway: SupervisedLiveTradingGateway) -> bool:
        barrier.wait(timeout=5)
        return gateway.submit(
            intent, approval=approval, market=_market(), submitted_at=NOW
        ).accepted

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, gateways))
    assert sum(results) == 1
    assert adapter.submitted_intents == (intent,)


def test_timeout_blocks_retries_and_new_intents_across_restart(tmp_path: Path) -> None:
    class TimeoutAdapter(FakeLiveAdapter):
        def submit_order(self, intent: OrderIntent) -> ExchangeOrder:
            super().submit_order(intent)
            raise TimeoutError("response lost after order reached exchange")

    adapter = TimeoutAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    intent = _approved_intent()
    result = gateway.submit(intent, approval=_approval(intent), market=_market(), submitted_at=NOW)
    assert not result.accepted
    assert "outcome unknown; reconciliation required" in result.reason
    restarted = _enabled_gateway(adapter, tmp_path)
    duplicate = restarted.submit(
        intent, approval=_approval(intent), market=_market(), submitted_at=NOW
    )
    assert "already been consumed" in duplicate.reason
    other = _approved_intent()
    blocked = restarted.submit(other, approval=_approval(other), market=_market(), submitted_at=NOW)
    assert not blocked.accepted
    assert "previous submission requires reconciliation" in blocked.reason
    assert adapter.submitted_intents == (intent,)


def test_crash_after_reservation_blocks_submission_on_restart(tmp_path: Path) -> None:
    intent = _approved_intent()
    ledger = LiveSubmissionLedger(tmp_path / "submissions.sqlite")
    ledger.reserve(intent, approval_id=None, exchange_name="fake-live", reserved_at=NOW)
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    other = _approved_intent()
    result = gateway.submit(other, approval=_approval(other), market=_market(), submitted_at=NOW)
    assert not result.accepted
    assert "reconciliation" in result.reason
    assert not adapter.submitted_intents


def test_missing_ledger_fails_closed_without_recreating_it(tmp_path: Path) -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    path = tmp_path / "submissions.sqlite"
    path.unlink()
    intent = _approved_intent()
    result = gateway.submit(intent, approval=_approval(intent), market=_market(), submitted_at=NOW)
    assert not result.accepted
    assert "ledger unavailable; no order sent" in result.reason
    assert not path.exists()
    assert not adapter.submitted_intents


def test_outcome_storage_failure_keeps_reconciliation_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise OperationalError("disk full")

    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    monkeypatch.setattr(LiveSubmissionLedger, "record_outcome", fail)
    intent = _approved_intent()
    result = gateway.submit(intent, approval=_approval(intent), market=_market(), submitted_at=NOW)
    assert not result.accepted
    assert "attempted but result could not be persisted" in result.reason
    other = _approved_intent()
    result = _enabled_gateway(adapter, tmp_path).submit(
        other,
        approval=_approval(other),
        market=_market(),
        submitted_at=NOW,
    )
    assert "reconciliation" in result.reason
    assert len(adapter.submitted_intents) == 1


@pytest.mark.parametrize("offset", [-31, 3])
def test_gateway_rejects_stale_or_future_submission_time(tmp_path: Path, offset: int) -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    intent = _approved_intent()
    result = gateway.submit(
        intent,
        approval=_approval(intent),
        market=_market(),
        submitted_at=NOW + timedelta(seconds=offset),
    )
    assert not result.accepted
    assert "submission timestamp" in result.reason
    assert not adapter.submitted_intents


def test_inputs_are_rechecked_after_storage_wait(tmp_path: Path) -> None:
    adapter = FakeLiveAdapter()
    times = iter((NOW, NOW + timedelta(seconds=31), NOW + timedelta(seconds=31)))
    gateway = SupervisedLiveTradingGateway(
        adapter=adapter,
        config=SupervisedLiveGatewayConfig(
            enable_supervised_live=True,
            runtime_live_execution_supported=True,
        ),
        submission_ledger=LiveSubmissionLedger(tmp_path / "submissions.sqlite"),
        clock=lambda: next(times),
    )
    intent = _approved_intent()
    result = gateway.submit(intent, approval=_approval(intent), market=_market(), submitted_at=NOW)
    assert not result.accepted
    assert "market snapshot is stale" in result.reason
    assert not adapter.submitted_intents


def test_in_memory_submission_ledger_is_not_allowed() -> None:
    with pytest.raises(ValueError, match="persistent file"):
        LiveSubmissionLedger(Path(":memory:"))


def test_mismatched_exchange_response_requires_reconciliation(tmp_path: Path) -> None:
    class MismatchAdapter(FakeLiveAdapter):
        def submit_order(self, intent: OrderIntent) -> ExchangeOrder:
            return replace(super().submit_order(intent), intent=_approved_intent())

    adapter = MismatchAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    intent = _approved_intent()
    result = gateway.submit(intent, approval=_approval(intent), market=_market(), submitted_at=NOW)
    assert not result.accepted
    assert "response mismatch; reconciliation required" in result.reason
    other = _approved_intent()
    blocked = _enabled_gateway(adapter, tmp_path).submit(
        other,
        approval=_approval(other),
        market=_market(),
        submitted_at=NOW,
    )
    assert not blocked.accepted
    assert "reconciliation" in blocked.reason
    assert len(adapter.submitted_intents) == 1


def test_invalid_approval_does_not_consume_an_unused_intent(tmp_path: Path) -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    intent = _approved_intent()
    result = gateway.submit(intent, approval=None, market=_market(), submitted_at=NOW)
    assert not result.accepted
    assert gateway.submit(
        intent,
        approval=_approval(intent),
        market=_market(),
        submitted_at=NOW,
    ).accepted
    assert adapter.submitted_intents == (intent,)


def test_approval_expiring_during_storage_wait_cannot_reach_adapter(tmp_path: Path) -> None:
    adapter = FakeLiveAdapter()
    times = iter((NOW, NOW + timedelta(minutes=5), NOW + timedelta(minutes=5)))
    gateway = SupervisedLiveTradingGateway(
        adapter=adapter,
        config=SupervisedLiveGatewayConfig(
            enable_supervised_live=True,
            runtime_live_execution_supported=True,
            preflight_config=LivePreflightConfig(
                max_market_age=timedelta(minutes=5),
                max_account_age=timedelta(minutes=5),
            ),
        ),
        submission_ledger=LiveSubmissionLedger(tmp_path / "submissions.sqlite"),
        clock=lambda: next(times),
    )
    intent = _approved_intent()
    result = gateway.submit(intent, approval=_approval(intent), market=_market(), submitted_at=NOW)
    assert not result.accepted
    assert "approval token is expired" in result.reason
    assert not adapter.submitted_intents


def test_historical_client_timestamps_cannot_override_gateway_clock(tmp_path: Path) -> None:
    adapter = FakeLiveAdapter()
    gateway = SupervisedLiveTradingGateway(
        adapter=adapter,
        config=SupervisedLiveGatewayConfig(
            enable_supervised_live=True,
            runtime_live_execution_supported=True,
        ),
        submission_ledger=LiveSubmissionLedger(tmp_path / "submissions.sqlite"),
        clock=lambda: NOW + timedelta(days=1),
    )
    intent = _approved_intent()
    result = gateway.submit(intent, approval=_approval(intent), market=_market(), submitted_at=NOW)
    assert not result.accepted
    assert "submission timestamp is stale" in result.reason
    assert not adapter.submitted_intents


def test_persistent_halt_is_enforced_by_every_gateway_instance(tmp_path: Path) -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    ledger = LiveSubmissionLedger(tmp_path / "submissions.sqlite")
    ledger.set_halt(reason="operator emergency stop", occurred_at=NOW)
    intent = _approved_intent()
    result = gateway.submit(intent, approval=_approval(intent), market=_market(), submitted_at=NOW)
    assert not result.accepted and "halted" in result.reason
    restarted = _enabled_gateway(adapter, tmp_path)
    assert not restarted.submit(
        intent, approval=_approval(intent), market=_market(), submitted_at=NOW
    ).accepted
    assert not adapter.submitted_intents
    ledger.resume_after_review(reason="operator reviewed isolated test", occurred_at=NOW)
    assert restarted.submit(
        intent, approval=_approval(intent), market=_market(), submitted_at=NOW
    ).accepted


def test_halt_during_reservation_prevents_exchange_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = FakeLiveAdapter()
    gateway = _enabled_gateway(adapter, tmp_path)
    reserve = LiveSubmissionLedger.reserve

    def reserve_then_halt(self: LiveSubmissionLedger, *args: object, **kwargs: object) -> None:
        reserve(self, *args, **kwargs)  # type: ignore[arg-type]
        self.set_halt(reason="emergency while reserving", occurred_at=NOW)

    monkeypatch.setattr(LiveSubmissionLedger, "reserve", reserve_then_halt)
    intent = _approved_intent()
    result = gateway.submit(intent, approval=_approval(intent), market=_market(), submitted_at=NOW)
    assert not result.accepted and "halted" in result.reason
    assert not adapter.submitted_intents


def _enabled_gateway(adapter: FakeLiveAdapter, tmp_path: Path) -> SupervisedLiveTradingGateway:
    return SupervisedLiveTradingGateway(
        adapter=adapter,
        config=SupervisedLiveGatewayConfig(
            enable_supervised_live=True,
            runtime_live_execution_supported=True,
        ),
        submission_ledger=LiveSubmissionLedger(tmp_path / "submissions.sqlite"),
        clock=lambda: NOW,
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
        account_checked_at=NOW,
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
