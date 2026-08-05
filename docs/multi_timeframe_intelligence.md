# Multi-Timeframe Intelligence

Stage 051 adds an advisory multi-timeframe intelligence engine over monthly,
weekly, daily, four-hour, and one-hour market evidence. It evaluates trend,
momentum, volatility, volume, market structure, support/resistance, and
liquidity to produce explainable alignment and timing context.

This stage does not create executable strategy signals, risk decisions, order
intents, exchange calls, order execution, real provider calls, or live trading.

## Inputs

Each `TimeframeObservation` includes:

- timeframe
- trend bias
- trend strength
- momentum score
- volatility score
- volume score
- market-structure score
- support/resistance score
- liquidity score
- quality status
- source reference

All inputs are supplied by deterministic fixtures or future stored analytics.

## Outputs

`MultiTimeframeIntelligence` includes:

- higher-timeframe bias
- trend alignment score
- trend strength
- timeframe agreement percentage
- entry timing score
- exit timing score
- market structure label
- high-confidence context flag
- rejection reasons
- risk rules
- evidence records
- quality status
- audit payload

## Safety Rules

The engine fails closed when required timeframes are missing, stale, rejected, or
contradict the higher-timeframe bias. A specific no-alignment case is blocked
when monthly and weekly are bearish while daily is bullish.

Multi-timeframe intelligence is advisory context only. Future strategy and risk
modules may consume it, but every trading action must still pass the Strategy
Engine, supervised live gateway controls, preflight checks, and the Risk
Management Engine. No profit is guaranteed.
