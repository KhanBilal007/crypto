"""Reproducible BTC strategy comparison on chronological public Binance candles."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from abtp.backtesting.metrics import calculate_max_drawdown
from abtp.dashboard.paper_app import (
    PAIR,
    MultiTimeframePaperStrategy,
    _daily_confirmation_from_candles,
    _dashboard_risk_policy,
    _snapshot,
)
from abtp.domain import Candle
from abtp.exchanges.binance import _kline_to_candle
from abtp.paper import (
    PaperAccountConfig,
    PaperTradingAccount,
    PaperTradingConfig,
    PaperTradingEngine,
)
from abtp.paper.simulator import PaperFillSimulationConfig
from abtp.paper.trade_metrics import trade_metrics
from abtp.strategies import (
    BreakoutStrategy,
    MinRiskSpotStrategyV1,
    StrategyPlugin,
    SupportResistanceReboundStrategy,
    TrendPullbackStrategy,
)


def download_candles(days: int) -> dict[str, Any]:
    end = datetime.now(UTC)
    start = end - timedelta(days=days + 7)
    result: dict[str, Any] = {
        "retrieved_at": end.isoformat(),
        "source": "Binance public spot klines",
    }
    for interval in ("1h", "1d"):
        rows: list[Any] = []
        cursor = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        while cursor < end_ms:
            query = urlencode(
                {
                    "symbol": "BTCUSDT",
                    "interval": interval,
                    "startTime": cursor,
                    "endTime": end_ms,
                    "limit": 1000,
                }
            )
            with urlopen(f"https://api.binance.com/api/v3/klines?{query}", timeout=30) as response:
                page = json.load(response)
            if not isinstance(page, list):
                raise ValueError("unexpected Binance kline response")
            if not page:
                break
            closed = [row for row in page if row[6] <= end_ms]
            rows.extend(closed)
            next_cursor = page[-1][0] + 1
            if next_cursor <= cursor:
                raise ValueError("Binance pagination did not advance")
            cursor = next_cursor
            if len(page) < 1000:
                break
        result[interval] = rows
    return result


def parse_candles(payload: dict[str, Any], interval: str) -> tuple[Candle, ...]:
    candles = tuple(_kline_to_candle(PAIR, interval, row) for row in payload[interval])
    delta = timedelta(hours=1) if interval == "1h" else timedelta(days=1)
    for previous, current in zip(candles, candles[1:], strict=False):
        if current.opened_at - previous.opened_at != delta:
            raise ValueError(f"{interval} data contains a missing, duplicate, or unordered candle")
    if not candles:
        raise ValueError("historical candle data is empty")
    return candles


def evaluate(
    strategy: StrategyPlugin,
    hourly: tuple[Candle, ...],
    daily: tuple[Candle, ...],
    *,
    start: datetime,
    end: datetime,
    slippage_bps: Decimal,
) -> dict[str, Any]:
    wrapper = MultiTimeframePaperStrategy(strategy, _daily_confirmation_from_candles(()))
    engine = PaperTradingEngine(
        strategy=wrapper,
        config=PaperTradingConfig(
            timeframe="1h",
            order_quantity=Decimal("0.01"),
            minimum_history=50,
            allow_pyramiding=False,
            max_drawdown_halt_pct=Decimal("0.05"),
            fill_simulation=PaperFillSimulationConfig(slippage_bps=slippage_bps),
        ),
        account=PaperTradingAccount(PaperAccountConfig(initial_cash=Decimal("10000"))),
        risk_policy=_dashboard_risk_policy(),
    )
    reasons: Counter[str] = Counter()
    signals: Counter[str] = Counter()
    executed_bars = 0
    mark = Decimal("1")
    first_price: Decimal | None = None
    for index, candle in enumerate(hourly[:-1]):
        if candle.closed_at < start - timedelta(hours=60) or candle.closed_at >= end:
            continue
        is_test = candle.closed_at >= start
        wrapper.update_daily_confirmation(
            _daily_confirmation_from_candles(
                tuple(item for item in daily if item.closed_at <= candle.closed_at)
            )
        )
        result = engine.on_market_update(
            _snapshot(index, candle.close, candle=candle, exchange_name="binance"),
            execute=is_test,
            execution_reference_price=hourly[index + 1].open,
        )
        mark = candle.close
        if is_test:
            first_price = first_price or hourly[index + 1].open
            executed_bars += 1
            if result.strategy_evaluation is not None:
                signals[result.strategy_evaluation.signal.direction.value] += 1
                reasons.update(result.strategy_evaluation.reasons)
            if result.skipped_reason:
                reasons[result.skipped_reason] += 1
            if result.risk_decision_status == "rejected":
                reasons["risk_engine_rejected"] += 1
    pnl = engine.account.equity(mark) - engine.account.config.initial_cash
    return {
        "strategy": strategy.config.name,
        "version": strategy.config.version,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "observed_test_bars": executed_bars,
        "signals": dict(signals),
        "paper_pnl_usdt": str(pnl),
        "return_pct": str(pnl / Decimal("100")),
        "max_drawdown_pct": str(calculate_max_drawdown(engine.account.state.equity_history) * 100),
        "fees_usdt": str(engine.account.state.fees_paid),
        "open_btc": str(engine.account.state.base_quantity),
        "buy_hold_gross_pct": str((mark / first_price - 1) * 100) if first_price else None,
        "top_reasons": reasons.most_common(8),
        **trade_metrics(engine.account.trades),
    }


def legacy_strategies(ref: str) -> tuple[StrategyPlugin, ...]:
    # Read the named commit without modifying the working tree.
    source = subprocess.check_output(
        ["git", "show", f"{ref}:src/abtp/strategies/swing.py"],
        text=True,
    )
    module = ModuleType("abtp_validation_legacy_swing")
    sys.modules[module.__name__] = module
    exec(compile(source, f"{ref}:swing.py", "exec"), module.__dict__)
    return (
        module.TrendPullbackStrategy(),
        module.BreakoutStrategy(),
        module.SupportResistanceReboundStrategy(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--baseline-ref")
    args = parser.parse_args()
    if args.days < 60:
        parser.error("at least 60 days are required for a separate 30-day test window")
    if args.download:
        args.data.parent.mkdir(parents=True, exist_ok=True)
        args.data.write_text(json.dumps(download_candles(args.days)), encoding="utf-8")
    raw = args.data.read_bytes()
    payload = json.loads(raw)
    hourly = parse_candles(payload, "1h")
    daily = parse_candles(payload, "1d")
    end = hourly[-1].opened_at
    start = end - timedelta(days=args.days)
    if hourly[0].closed_at > start - timedelta(hours=60) or daily[0].closed_at > start - timedelta(
        days=4
    ):
        raise ValueError("dataset is too short for the requested evaluation and warmup")
    groups: dict[str, tuple[StrategyPlugin, ...]] = {
        "candidate": (
            MinRiskSpotStrategyV1(),
            TrendPullbackStrategy(),
            BreakoutStrategy(),
            SupportResistanceReboundStrategy(),
        )
    }
    if args.baseline_ref:
        groups["legacy_rules_fixed_execution"] = legacy_strategies(args.baseline_ref)
    rows = []
    for label, strategies in groups.items():
        for window, window_start, window_end in (
            ("first_period", start, end - timedelta(days=30)),
            ("last_30_days", end - timedelta(days=30), end),
        ):
            for slippage in (Decimal("5"), Decimal("10")):
                for strategy in strategies:
                    row = evaluate(
                        strategy,
                        hourly,
                        daily,
                        start=window_start,
                        end=window_end,
                        slippage_bps=slippage,
                    )
                    rows.append(
                        {"group": label, "window": window, "slippage_bps": str(slippage), **row}
                    )
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "data_sha256": hashlib.sha256(raw).hexdigest(),
        "data_source": payload["source"],
        "retrieved_at": payload["retrieved_at"],
        "baseline_ref": args.baseline_ref,
        "assumptions": {
            "initial_cash_usdt": "10000",
            "max_btc_per_entry": "0.01",
            "fee_bps_each_side": "20",
            "spread_bps": "10",
            "max_risk_per_trade_pct": "0.25",
            "entry_and_signal_exit": "next candle open with spread/slippage",
            "protective_exits": "bar high/low, stop first on ambiguity, adverse gap price",
            "daily_confirmation": "only daily candles closed by signal time",
            "legacy_comparison": (
                "old strategy rules on the same corrected execution/indicator pipeline"
            ),
            "parameter_search": "none; rule changes specified before viewing results",
            "limitations": (
                "No historical order book or tick fills; small samples are not proof of an edge. "
                "Last 30 days are a chronological check, "
                "not a pristine unseen holdout after this audit."
            ),
        },
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(args.output), "comparisons": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
