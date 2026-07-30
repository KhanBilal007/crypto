# Walk-Forward Validation

Stage 039 adds deterministic walk-forward validation evidence for strategy
promotion. It is advisory only. It does not create strategy signals, risk
decisions, order intents, exchange calls, order execution, or live strategy
changes.

## Inputs

`TimeSeriesSplitPolicy` creates deterministic train/test windows from ordered
timestamps. The current utilities support fixed rolling windows, expanding
windows, and a time-series cross-validation alias.

`WindowMetricResult` records one validation window:

- explicit train and out-of-sample test window boundaries
- in-sample `PerformanceMetrics`
- out-of-sample `PerformanceMetrics`
- optional strategy parameters
- data-quality status
- source references

The module consumes existing backtesting/reporting metrics. It does not run a
new backtest engine by itself and does not connect to exchanges.

## Robustness Scoring

`RobustnessPolicy` applies conservative promotion thresholds:

- minimum number of validation windows
- minimum out-of-sample pass ratio
- minimum average out-of-sample return
- maximum out-of-sample drawdown
- maximum tail loss
- minimum profit factor
- maximum train/test return gap
- minimum parameter stability
- required regime coverage when configured
- required fee and slippage inclusion

The robustness score is built from pass ratio, out-of-sample return, drawdown,
train/test gap, and parameter stability. Rejection reasons are preserved so an
operator can see why a strategy is not eligible for promotion.

## Overfit Rejection

Strategies are rejected when in-sample results are much stronger than
out-of-sample results, when parameter values are unstable across windows, or
when out-of-sample results fail risk-first thresholds. Positive returns in one
window are not enough to pass.

## Auditability

`WalkForwardValidationReport` includes:

- all split boundaries
- each window's in-sample and out-of-sample metrics
- robustness score
- regime coverage
- rejected reasons
- source references
- compact audit payload

Every report can be serialized with `as_dict()` and linked to future optimiser,
laboratory, paper-trading, or operator-dashboard records.

## Operating Limits

- Validation output is evidence only, not a signal.
- Rejected strategies must not be promoted automatically.
- All future signals must still pass the Strategy Engine.
- All future order paths must still pass the Risk Management Engine.
- Poor-quality windows fail closed.
- No real exchange/API calls or external providers are used.
- No profit is guaranteed.
