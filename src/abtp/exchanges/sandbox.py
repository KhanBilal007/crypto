"""Deterministic sandbox exchange connector."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

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
    RiskDecisionStatus,
)
from abtp.exchanges.base import (
    Balance,
    ExchangeMode,
    ExchangeOrder,
    ExchangeSymbol,
    RateLimitState,
    Ticker,
)
from abtp.exchanges.errors import (
    InvalidSymbolError,
    OrderRejectedError,
    RateLimitExceededError,
    StaleDataError,
    UnsafeLiveOperationError,
    UnsupportedOperationError,
)


class SandboxExchangeAdapter:
    """Fixture-driven sandbox exchange with no real network behavior."""

    def __init__(
        self,
        *,
        now: datetime,
        mode: ExchangeMode = ExchangeMode.SANDBOX,
        symbols: tuple[ExchangeSymbol, ...] | None = None,
        balances: tuple[Balance, ...] | None = None,
        prices: dict[str, Decimal] | None = None,
        rate_limit: int = 100,
        latency_ms: int = 0,
        websocket_connected: bool = False,
        live_credentials_present: bool = False,
    ) -> None:
        if mode is ExchangeMode.LIVE:
            raise UnsafeLiveOperationError("sandbox adapter cannot be constructed in live mode")
        if live_credentials_present:
            raise UnsafeLiveOperationError("sandbox adapter rejects live credential presence")
        if rate_limit <= 0:
            raise ValueError("rate_limit must be positive")
        self._name = "sandbox"
        self._mode = mode
        self._now = now
        self._symbols = symbols or (_default_symbol(),)
        self._symbol_by_pair = {symbol.pair.symbol: symbol for symbol in self._symbols}
        self._balances = {
            balance.asset.symbol: balance for balance in balances or _default_balances()
        }
        self._prices = prices or {"BTC/USDT": Decimal("100000")}
        self._rate_limit = rate_limit
        self._remaining = rate_limit
        self._reset_at = now + timedelta(minutes=1)
        self._latency_ms = latency_ms
        self._websocket_connected = websocket_connected
        self._orders: dict[str, ExchangeOrder] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def mode(self) -> ExchangeMode:
        return self._mode

    @property
    def latency_ms(self) -> int:
        return self._latency_ms

    @property
    def websocket_connected(self) -> bool:
        return self._websocket_connected

    def symbols(self) -> tuple[ExchangeSymbol, ...]:
        self._consume_rate_limit()
        return self._symbols

    def balances(self) -> tuple[Balance, ...]:
        self._consume_rate_limit()
        return tuple(self._balances.values())

    def ticker(self, pair: AssetPair) -> Ticker:
        self._consume_rate_limit()
        self._require_symbol(pair)
        return Ticker(
            pair=pair,
            price=self._prices[pair.symbol],
            captured_at=self._now,
            source_ref=f"sandbox:ticker:{pair.symbol}:{self._now.isoformat()}",
        )

    def candles(self, pair: AssetPair, interval: str, limit: int) -> tuple[Candle, ...]:
        self._consume_rate_limit()
        self._require_symbol(pair)
        if limit <= 0:
            raise ValueError("limit must be positive")
        price = self._prices[pair.symbol]
        exchange = Exchange(self.name)
        candles: list[Candle] = []
        for index in range(limit):
            opened_at = self._now - timedelta(minutes=limit - index)
            closed_at = opened_at + timedelta(minutes=1)
            candles.append(
                Candle(
                    exchange=exchange,
                    pair=pair,
                    interval=interval,
                    opened_at=opened_at,
                    closed_at=closed_at,
                    open=price,
                    high=price + Decimal("10"),
                    low=price - Decimal("10"),
                    close=price,
                    volume=Decimal("1"),
                )
            )
        return tuple(candles)

    def order_book(self, pair: AssetPair) -> OrderBookSnapshot:
        self._consume_rate_limit()
        self._require_symbol(pair)
        price = self._prices[pair.symbol]
        return OrderBookSnapshot(
            exchange=Exchange(self.name),
            pair=pair,
            captured_at=self._now,
            bids=(OrderBookLevel(price - Decimal("1"), Decimal("1")),),
            asks=(OrderBookLevel(price + Decimal("1"), Decimal("1")),),
            source_ref=f"sandbox:book:{pair.symbol}:{self._now.isoformat()}",
        )

    def submit_order(self, intent: OrderIntent) -> ExchangeOrder:
        self._consume_rate_limit()
        symbol = self._require_symbol(intent.pair)
        self._require_risk_approval(intent)
        self._validate_order_shape(intent, symbol)
        price = self._execution_price(intent)
        notional = intent.quantity * price
        self._require_balances(intent, notional)
        self._apply_fill(intent, price, symbol)

        exchange_order = ExchangeOrder(
            exchange_order_id=f"sandbox-{uuid4()}",
            intent=intent,
            status=OrderStatus.FILLED,
            submitted_at=self._now,
            filled_quantity=intent.quantity,
            average_fill_price=price,
            fee_paid=notional * symbol.taker_fee_bps / Decimal("10000"),
        )
        self._orders[exchange_order.exchange_order_id] = exchange_order
        return exchange_order

    def get_order(self, exchange_order_id: str) -> ExchangeOrder:
        self._consume_rate_limit()
        try:
            return self._orders[exchange_order_id]
        except KeyError as exc:
            raise OrderRejectedError(f"unknown sandbox order: {exchange_order_id}") from exc

    def cancel_order(self, exchange_order_id: str) -> ExchangeOrder:
        self._consume_rate_limit()
        order = self.get_order(exchange_order_id)
        if order.status is OrderStatus.FILLED:
            raise OrderRejectedError("filled sandbox orders cannot be canceled")
        canceled = replace(order, status=OrderStatus.CANCELED)
        self._orders[exchange_order_id] = canceled
        return canceled

    def rate_limit_state(self) -> RateLimitState:
        return RateLimitState(
            limit=self._rate_limit,
            remaining=self._remaining,
            reset_at=self._reset_at,
        )

    def withdraw(self, asset: Asset, quantity: Decimal) -> None:
        raise UnsupportedOperationError("withdrawals are disabled in Stage 009")

    def enable_margin(self) -> None:
        raise UnsupportedOperationError("margin is disabled in Stage 009")

    def _consume_rate_limit(self) -> None:
        if self._remaining <= 0:
            raise RateLimitExceededError("sandbox rate limit exceeded")
        self._remaining -= 1

    def _require_symbol(self, pair: AssetPair) -> ExchangeSymbol:
        try:
            return self._symbol_by_pair[pair.symbol]
        except KeyError as exc:
            raise InvalidSymbolError(f"unsupported sandbox symbol: {pair.symbol}") from exc

    def _require_risk_approval(self, intent: OrderIntent) -> None:
        decision = intent.risk_decision
        if decision is None:
            raise OrderRejectedError("sandbox orders require a risk-approved OrderIntent")
        if decision.order_intent_id != intent.id:
            raise OrderRejectedError("risk decision does not match order intent")
        if decision.status is not RiskDecisionStatus.APPROVED or not decision.allowed:
            raise OrderRejectedError("risk decision rejected the order intent")
        if decision.kill_switch_active:
            raise OrderRejectedError("kill switch is active")

    def _validate_order_shape(self, intent: OrderIntent, symbol: ExchangeSymbol) -> None:
        if intent.quantity < symbol.min_order_size:
            raise OrderRejectedError("order quantity is below min_order_size")
        if intent.quantity % symbol.lot_size != Decimal("0"):
            raise OrderRejectedError("order quantity does not align to lot_size")
        if intent.order_type is OrderType.LIMIT:
            if intent.limit_price is None:
                raise OrderRejectedError("limit order requires limit_price")
            if intent.limit_price % symbol.tick_size != Decimal("0"):
                raise OrderRejectedError("limit_price does not align to tick_size")

    def _execution_price(self, intent: OrderIntent) -> Decimal:
        price = self._prices[intent.pair.symbol]
        if self._now - intent.created_at > timedelta(minutes=5):
            raise StaleDataError("order intent is stale for sandbox execution")
        return intent.limit_price or price

    def _require_balances(self, intent: OrderIntent, notional: Decimal) -> None:
        if intent.side is OrderSide.BUY:
            available = self._balances[intent.pair.quote.symbol].available
            if available < notional:
                raise OrderRejectedError("insufficient quote balance")
            return
        available = self._balances[intent.pair.base.symbol].available
        if available < intent.quantity:
            raise OrderRejectedError("insufficient base balance")

    def _apply_fill(self, intent: OrderIntent, price: Decimal, symbol: ExchangeSymbol) -> None:
        base = intent.pair.base.symbol
        quote = intent.pair.quote.symbol
        notional = intent.quantity * price
        fee = notional * symbol.taker_fee_bps / Decimal("10000")
        base_balance = self._balances[base]
        quote_balance = self._balances[quote]
        if intent.side is OrderSide.BUY:
            self._balances[base] = Balance(
                base_balance.asset,
                base_balance.available + intent.quantity,
            )
            self._balances[quote] = Balance(
                quote_balance.asset,
                quote_balance.available - notional - fee,
            )
        else:
            self._balances[base] = Balance(
                base_balance.asset,
                base_balance.available - intent.quantity,
            )
            self._balances[quote] = Balance(
                quote_balance.asset,
                quote_balance.available + notional - fee,
            )


def _default_symbol() -> ExchangeSymbol:
    return ExchangeSymbol(
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        tick_size=Decimal("0.01"),
        lot_size=Decimal("0.0001"),
        min_order_size=Decimal("0.0001"),
        maker_fee_bps=Decimal("10"),
        taker_fee_bps=Decimal("20"),
    )


def _default_balances() -> tuple[Balance, ...]:
    return (
        Balance(Asset("BTC"), Decimal("1")),
        Balance(Asset("USDT"), Decimal("1000000")),
    )
