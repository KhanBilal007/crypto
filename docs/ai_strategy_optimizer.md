# AI Strategy Optimiser

Stage 038 scores strategy candidates and recommends the most suitable strategy
for the current market regime. It is advisory only. It does not create strategy
signals, risk decisions, order intents, exchange calls, order execution, or
unsupervised live strategy changes.

## Inputs

`StrategyMetricSnapshot` accepts:

- strategy name
- backtest, paper, or later live `PerformanceMetrics`
- optional recent metrics for stability checks
- data-quality status
- source references

`StrategyOptimisationRequest` adds:

- current market regime label
- runtime mode: research, backtest, paper, or live
- manual approval flag for live strategy changes
- risk-limits reference
- source references

## Scoring

The scoring policy considers:

- win rate
- expectancy
- drawdown
- Sharpe ratio
- profit factor
- regime suitability
- stability between historical and recent metrics
- confidence based on sample size, cost inclusion, and win rate

Strategies are rejected when sample size is insufficient, costs are missing,
drawdown exceeds limits, profit factor is below the limit, metric quality is not
trusted, or there is insufficient evidence for the current regime.

## Selection

The selector chooses the highest eligible strategy above the configured score
threshold. Underperforming strategies can be recommended for automatic disable
only in research or paper mode. Live strategy changes require manual approval
and remain advisory.

## Auditability

Every report includes ranked scores, component values, evidence strings,
rejected reasons, selected strategy, risk-limits reference, source references,
and a compact audit payload.

## Operating Limits

- Optimiser recommendations are not trading signals.
- All future signals must still be created by the Strategy Engine.
- All future order paths must still pass the Risk Management Engine.
- Poor data quality or insufficient sample size fails closed.
- No real exchange/API calls or external providers are used.
- No profit is guaranteed.
