from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.data import OrderBookMetrics, StreamHealth
from abtp.domain import (
    Asset,
    AssetPair,
    Candle,
    Exchange,
    OrderSide,
    OrderStatus,
    Signal,
    SignalDirection,
)
from abtp.execution import ExecutionResult
from abtp.paper import (
    PaperAccountConfig,
    PaperFillSimulationConfig,
    PaperMarketSnapshot,
    PaperTradingAccount,
    PaperTradingConfig,
    PaperTradingEngine,
    estimate_paper_fill,
)
from abtp.strategies import MinRiskSpotStrategyV1
from abtp.strategies.base import (
    StrategyConfig,
    StrategyContext,
    StrategyEvaluation,
    StrategySignalPlan,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PAIR = AssetPair(Asset("BTC"), Asset("USDT"))


def test_paper_engine_simulates_fills_through_execution_contract() -> None:
    engine = PaperTradingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=PaperTradingConfig(timeframe="1h", order_quantity=Decimal("0.01")),
    )

    results = [
        engine.on_market_update(_snapshot(index, close))
        for index, close in enumerate(("100", "101", "102", "104"))
    ]
    executed = [result for result in results if result.executed]

    assert executed
    assert isinstance(executed[0].execution_result, ExecutionResult)
    assert executed[0].execution_result.status is OrderStatus.FILLED
    assert executed[0].risk_decision_status == "approved"
    assert engine.account.trades
    assert engine.account.state.fees_paid > Decimal("0")


def test_degraded_live_data_blocks_strategy_and_orders() -> None:
    engine = PaperTradingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=PaperTradingConfig(timeframe="1h"),
    )

    result = engine.on_market_update(_snapshot(0, "100", degraded=True))

    assert result.skipped_reason == "live data is degraded"
    assert result.strategy_evaluation is None
    assert result.execution_result is None
    assert not engine.account.trades


def test_drawdown_halt_blocks_later_paper_entries() -> None:
    engine = PaperTradingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=PaperTradingConfig(
            timeframe="1h",
            order_quantity=Decimal("1"),
            max_drawdown_halt_pct=Decimal("0.001"),
        ),
        account=PaperTradingAccount(PaperAccountConfig(initial_cash=Decimal("10000"))),
    )

    for index, close in enumerate(("100", "101", "102", "104")):
        engine.on_market_update(_snapshot(index, close))
    halted = engine.on_market_update(_snapshot(4, "70"))

    assert halted.skipped_reason == "paper drawdown halt active"
    assert halted.execution_result is None


def test_direct_order_submission_is_blocked() -> None:
    engine = PaperTradingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=PaperTradingConfig(timeframe="1h"),
    )

    with pytest.raises(ValueError, match="risk-approved engine cycles"):
        engine.submit_order(object())


def test_paper_engine_respects_sell_strategy_signal() -> None:
    engine = PaperTradingEngine(
        strategy=_SellAfterEntryStrategy(),
        config=PaperTradingConfig(timeframe="1h", order_quantity=Decimal("0.01")),
        account=PaperTradingAccount(PaperAccountConfig(initial_cash=Decimal("10000"))),
    )

    engine.on_market_update(_snapshot(0, "100"))
    engine.on_market_update(_snapshot(1, "101"))

    trades = engine.account.trades
    assert [trade.side for trade in trades] == [OrderSide.BUY, OrderSide.SELL]
    assert engine.cycles[-1].risk_decision_status == "approved_exit"
    assert engine.account.state.base_quantity == Decimal("0.00")


def test_paper_fill_estimate_includes_spread_slippage_and_latency() -> None:
    estimate = estimate_paper_fill(
        reference_price=Decimal("100"),
        side=OrderSide.BUY,
        config=PaperFillSimulationConfig(
            fee_bps=Decimal("20"),
            spread_bps=Decimal("10"),
            slippage_bps=Decimal("5"),
            latency_ms=42,
        ),
    )

    assert estimate.execution_price == Decimal("100.100")
    assert estimate.latency_ms == 42


class _SellAfterEntryStrategy:
    def __init__(self) -> None:
        self._config = StrategyConfig(
            name="sell_after_entry_fixture",
            version="test",
            supported_timeframes=("1h",),
        )

    @property
    def config(self) -> StrategyConfig:
        return self._config

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        exposure = context.features.values.get("portfolio.exposure_base", Decimal("0"))
        direction = SignalDirection.SELL if exposure > Decimal("0") else SignalDirection.BUY
        return StrategyEvaluation(
            strategy_name=self.config.name,
            strategy_version=self.config.version,
            enabled=True,
            signal=Signal(
                source="sell_after_entry_fixture:test",
                pair=context.features.pair,
                generated_at=context.generated_at,
                direction=direction,
                confidence=Decimal("0.8"),
                inputs_ref=context.feature_snapshot_ref,
                rationale="fixture direction",
            ),
            plan=StrategySignalPlan(
                entry_reason="fixture direction",
                timeframe=context.timeframe,
                feature_snapshot_ref=context.feature_snapshot_ref,
                stop_suggestion=Decimal("99") if direction is SignalDirection.BUY else None,
            ),
            reasons=("fixture direction",),
            generated_at=context.generated_at,
        )


def _snapshot(
    index: int,
    close: str,
    *,
    degraded: bool = False,
) -> PaperMarketSnapshot:
    candle = _candle(index, Decimal(close))
    received_at = candle.closed_at + timedelta(seconds=1)
    return PaperMarketSnapshot(
        candle=candle,
        order_book_metrics=OrderBookMetrics(
            best_bid=candle.close - Decimal("0.01"),
            best_ask=candle.close + Decimal("0.01"),
            spread=Decimal("0.02"),
            bid_depth=Decimal("5"),
            ask_depth=Decimal("4"),
            imbalance=Decimal("0.1111111111111111111111111111"),
        ),
        health=StreamHealth(
            is_connected=not degraded,
            is_stale=False,
            is_degraded=degraded,
            disconnect_count=1 if degraded else 0,
            last_message_at=received_at,
            latency_ms=2000 if degraded else 10,
            stale_after=timedelta(seconds=30),
        ),
        received_at=received_at,
    )


def _candle(index: int, close: Decimal) -> Candle:
    opened_at = NOW + timedelta(hours=index)
    return Candle(
        exchange=Exchange("fixture"),
        pair=PAIR,
        interval="1h",
        opened_at=opened_at,
        closed_at=opened_at + timedelta(hours=1),
        open=close,
        high=close * Decimal("1.005"),
        low=close * Decimal("0.995"),
        close=close,
        volume=Decimal("1"),
    )
