# Market Regimes

Stage 018 adds an advisory market regime classifier for research, backtesting,
paper workflows, and future risk context. It classifies feature snapshots as
`trend_up`, `trend_down`, `range_bound`, `high_volatility`, `shock`, or
`unknown`.

## Inputs

The classifier consumes Stage 015 `FeatureSnapshot` objects and optional Stage
016 `ContextBatch` values. It uses only deterministic, already-normalized
inputs such as:

- `market.return_1`
- `market.return_3`
- `market.volume_ratio`
- `indicator.atr.atr_pct`
- `indicator.rsi.rsi`
- `indicator.sma.sma`
- `market.close`
- optional `liquidity.spread_bps`
- optional `portfolio.drawdown`
- optional context such as Bitcoin sentiment, liquidation spikes, or major
  calendar events

The classifier does not fetch exchange data, call external providers, train
models, emit signals, create order intents, make risk decisions, or execute
orders.

## Outputs

`RegimeClassification` contains:

- regime label
- confidence
- risk adjustment suggestion
- explanation reasons
- evidence entries with source references
- feature schema version
- generation timestamp
- data-quality status

Risk adjustment suggestions are advisory context for later risk modules. They
include `max_position_multiplier`, `block_new_entries`, `tighten_stops`,
`reduce_trade_frequency`, and a rationale.

## Safety Behavior

The classifier fails closed. Rejected feature quality, missing required inputs,
shock-sized returns, severe volatility, abnormal spreads, severe drawdown, or
sudden negative context will produce `unknown`, `high_volatility`, or `shock`
outputs with conservative risk suggestions. High-volatility and shock regimes
set `block_new_entries=true`.

External context remains optional and lower-trust by default. If optional
context contributes to a shock classification, the result is marked degraded so
future strategy and risk layers can choose conservative behavior.

## Operating Limits

Stage 018 is not a trading system. It only labels market state for future
decision cycles. Live trading remains disabled, and no profit is guaranteed.
Every regime result is explainable through stored feature values, optional
context items, quality flags, and generated evidence.
