# Continuous Performance Analytics

Stage 050 adds read-only performance analytics for daily, weekly, monthly, and
long-term operator review. It aggregates supplied or stored evidence from
trades, portfolio equity snapshots, risk breaches, predictions, regimes,
execution records, dashboard metrics, and audit references.

The analytics package does not change strategies, approve risk, create order
intents, submit orders, call exchanges, call external providers, or enable live
trading.

## Contracts

`src/abtp/analytics/performance.py` defines performance observations, standard
windows, and `PerformanceWindowReport`.

`src/abtp/analytics/trends.py` defines strategy/regime comparisons and AI
accuracy, risk, drawdown, and execution-quality trend reports.

`src/abtp/analytics/dashboard_metrics.py` defines read-only operator dashboard
metric snapshots.

Every report includes source references, quality status, limitations, and an
audit payload where appropriate.

## Included Metrics

Window reports include starting equity, ending equity, net P/L, net return,
maximum drawdown, total fees, average slippage, trade count, risk breach count,
AI prediction accuracy when available, execution quality when available,
strategy count, regime count, and observation count.

Trend reports include:

- AI accuracy trend
- risk breach trend
- drawdown trend
- execution quality trend

Dashboard snapshots expose summary metrics only. They do not add controls or
unsafe actions.

## Operating Limits

Performance analytics is advisory. Reports must be reviewed with costs, fees,
slippage, drawdown, risk breaches, and execution quality together. Positive
historical, backtest, or paper performance is not a profitability guarantee.
Any future trading action must still pass strategy rules, supervised live
gateway controls, preflight checks, and the Risk Management Engine.
