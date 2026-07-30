from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.backtesting import BacktestConfig, BacktestingEngine, SlippageModelConfig
from abtp.domain import Asset, AssetPair, Candle, Exchange, OrderStatus
from abtp.strategies import MinRiskSpotStrategyV1

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_backtest_replays_strategy_with_risk_and_paper_execution() -> None:
    engine = BacktestingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=BacktestConfig(
            timeframe="1h",
            initial_cash=Decimal("10000"),
            order_quantity=Decimal("0.01"),
        ),
    )

    result = engine.run(_candles(("100", "101", "102", "104", "106")))

    assert result.costs_included
    assert result.starting_equity == Decimal("10000")
    assert result.ending_equity > Decimal("0")
    assert result.risk_decision_count >= 1
    assert result.trades
    assert result.total_fees > Decimal("0")
    assert any(
        step.execution_result is not None and step.execution_result.status is OrderStatus.FILLED
        for step in result.steps
    )


def test_feature_generation_uses_only_candles_so_far() -> None:
    first_engine = BacktestingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=BacktestConfig(timeframe="1h"),
    )
    second_engine = BacktestingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=BacktestConfig(timeframe="1h"),
    )

    first = first_engine.run(_candles(("100", "101", "102", "104", "1000000")))
    second = second_engine.run(_candles(("100", "101", "102", "104", "1")))

    assert first.steps[3].features.values["market.close"] == Decimal("104")
    assert first.steps[3].features.values["market.return_3"] == Decimal("0.04")
    assert first.steps[3].features.values == second.steps[3].features.values
    assert first.steps[4].features.values != second.steps[4].features.values


def test_fee_and_slippage_are_included_in_fills() -> None:
    engine = BacktestingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=BacktestConfig(
            timeframe="1h",
            slippage=SlippageModelConfig(
                fee_bps=Decimal("20"),
                spread_bps=Decimal("10"),
                slippage_bps=Decimal("5"),
            ),
        ),
    )

    result = engine.run(_candles(("100", "101", "102", "104")))
    trade = result.trades[0]

    assert trade.price == Decimal("102.102")
    assert trade.fee_paid > Decimal("0")
    assert result.total_fees == sum((item.fee_paid for item in result.trades), Decimal("0"))
    assert result.costs_included


def test_drawdown_halt_blocks_new_execution_after_adverse_move() -> None:
    engine = BacktestingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=BacktestConfig(
            timeframe="1h",
            order_quantity=Decimal("5"),
            max_drawdown_halt_pct=Decimal("0.01"),
        ),
    )

    result = engine.run(_candles(("100", "101", "102", "104", "70", "71")))

    assert any(step.skipped_reason == "drawdown halt active" for step in result.steps)
    assert result.max_drawdown > Decimal("0.01")


def _candles(closes: tuple[str, ...]) -> tuple[Candle, ...]:
    return tuple(_candle(index, Decimal(close)) for index, close in enumerate(closes))


def _candle(index: int, close: Decimal) -> Candle:
    opened_at = NOW + timedelta(hours=index)
    return Candle(
        exchange=Exchange("fixture"),
        pair=AssetPair(Asset("BTC"), Asset("USDT")),
        interval="1h",
        opened_at=opened_at,
        closed_at=opened_at + timedelta(hours=1),
        open=close,
        high=close * Decimal("1.005"),
        low=close * Decimal("0.995"),
        close=close,
        volume=Decimal("1"),
    )
