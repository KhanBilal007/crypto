# AI Dataset and Baseline Model

Stage 017 adds deterministic AI research and backtesting utilities. It does not
implement advanced machine learning, live model serving, strategy signals, risk
decisions, order intents, order execution, real exchange connectors, real
external provider calls, or live trading.

## Datasets

`build_feature_dataset()` consumes Stage 015 `FeatureSnapshot` objects and
creates `DatasetRow` records. By default, non-live-eligible feature snapshots
are excluded. They can be included explicitly for research analysis, but are
marked non-actionable.

Dataset metadata records:

- feature schema version
- build timestamp
- stable feature names
- label horizon
- fee and slippage assumptions
- training window
- optional external context source references
- limitations

## Labels

Labels are generated from future windows:

- future return direction: up, down, or flat
- future return magnitude
- future volatility as mean absolute future-window return

Feature values come only from the current or past feature snapshot. Future
values are used only to label the row. Rows without enough future data are
omitted.

## Splits

`split_time_ordered()` and `dataset_with_splits()` preserve timestamp order and
do not shuffle rows. This keeps train, validation, and test windows from
overlapping or leaking future observations into earlier splits.

## Baseline

`ConservativeBaselineModel` is a dependency-free research baseline. It learns
simple training-set priors and applies a small current-return nudge. It emits:

- probability up
- probability down
- confidence
- expected return
- expected volatility
- model metadata
- quality/actionability status

The output may be converted to the Stage 007 `Prediction` domain contract for
storage, but it never creates buy/sell signals, risk decisions, order intents,
or executable orders.

## Metrics

Stage 017 includes deterministic metrics:

- accuracy
- precision/recall
- directional hit rate
- return mean absolute error
- volatility mean absolute error
- simple calibration buckets and calibration error

These metrics verify baseline behavior for research and backtesting only. They
are not profitability claims.

## Operating Limits

The baseline model is intentionally conservative and limited. It is not a
production trading model, does not guarantee profit, and is blocked from any
execution path. Future strategy and risk modules must continue to treat AI
output as one explainable input, not as trading authority.
