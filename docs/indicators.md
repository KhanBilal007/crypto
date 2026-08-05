# Technical Indicators

Stage 014 adds reusable technical indicators over normalized market candles. The
indicator layer is deterministic, read-only, and isolated from strategy, risk,
portfolio, execution, exchange, database, and AI model behavior.

## Contracts

Indicators consume tuples of `Candle` domain objects and return
`IndicatorResult` objects. Each result contains:

- `IndicatorMetadata`: name, parameters, lookback, warmup, source interval,
  calculation time, and indicator version.
- `values`: decimal indicator values.
- `quality`: a `DataQualityStatus` that is trusted, degraded, or rejected.

The default indicator version is `stage-014`.

## Engine

`IndicatorEngine` registers calculators by name and dispatches calculations
without coupling to strategy or AI modules. The default registry exposes:

- `sma`
- `ema`
- `macd`
- `vwap`
- `obv`
- `support_resistance`
- `rsi`
- `stochastic`
- `atr`
- `bollinger_bands`
- `adx`

New indicators can be registered with `IndicatorEngine.register()` as long as
they return `IndicatorResult`.

## Warmup and Quality

Every indicator declares a warmup requirement. If the caller supplies fewer
candles than required, the result is rejected with the `insufficient_data` flag
and no values.

If source candles are marked degraded, the indicator may still emit values, but
the result remains degraded and carries the source quality flags. If source data
is rejected, the indicator result is rejected and emits no values. Non-finite
numeric candle values are rejected with `invalid_numeric_value`.

## Operating Limits

Indicators emit values only. They cannot create trade signals, predictions,
risk decisions, order intents, exchange requests, or live trading actions.

No real exchange, database, news, on-chain, macro, derivatives, sentiment, AI,
strategy, risk, or execution logic is implemented in this stage.
