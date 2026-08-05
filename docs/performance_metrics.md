# Backtesting Reports and Performance Metrics

Stage 026 adds a reporting layer for historical backtests. Reports judge
strategy quality using risk-adjusted metrics and explicit acceptance gates, not
net return alone.

## Metrics

`src/abtp/backtesting/metrics.py` calculates:

- net return
- maximum drawdown
- profit factor
- Sharpe and Sortino ratios
- win rate
- expectancy
- average win and average loss
- exposure time
- worst observed period return as a conservative tail-loss proxy
- total fees
- trade count
- whether costs were included
- per-regime performance slices

Metrics are derived from `BacktestResult` equity, trades, fees, and cost flags.
No exchange, provider, strategy, risk, order execution, or live trading behavior
is added by this stage.

## Acceptance Gates

`src/abtp/backtesting/reports.py` converts metrics into an auditable
`BacktestReport`. The default gate requires:

- fees and slippage included
- maximum drawdown at or below the configured limit
- tail loss inside the configured limit
- non-negative net return
- profit factor at or above the configured threshold
- a minimum trade sample

A strategy fails paper-trading eligibility if drawdown or tail-loss checks fail,
even when net return is positive. This keeps validation risk-first.

## Report Contract

Each report contains:

- strategy name
- generated timestamp
- metric values
- regime performance by strategy-reported regime label
- per-gate pass/fail checks
- paper-trading eligibility flag
- source references
- limitations

The report is JSON-friendly through `BacktestReport.as_dict()`. Decimal values
are rendered as strings so downstream audit storage can preserve exact values.

## Operating Limits

Stage 026 reports are deterministic validation artifacts. They do not claim a
strategy is profitable, do not create signals, do not approve risk, do not build
orders, and do not execute trades. Eligibility means only that the configured
historical report gates passed for the tested assumptions and data.
