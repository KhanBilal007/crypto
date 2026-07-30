# Minimum-Risk Spot Strategy V1

Stage 021 adds the first concrete strategy plugin: `min_risk_spot_v1`.

The strategy is conservative, BTC-only, long-only, spot-first, and focused on
capital preservation. It emits non-executable `Signal` objects only.

## Inputs

The strategy consumes a Stage 020 `StrategyContext`:

- trusted Stage 015 feature snapshot
- Stage 018 regime classification
- optional Stage 019 prediction result
- timeframe
- immutable runtime state for cooldown and open-position checks

Required feature values include:

- `market.close`
- `market.return_3`
- `market.volume_ratio`
- `indicator.rsi.rsi`
- `indicator.atr.atr_pct`
- `liquidity.spread_bps`

## Entry Requirements

A BUY signal is emitted only when all conservative checks pass:

- base asset is BTC
- timeframe is supported
- feature quality is trusted
- no current BTC base position is supplied
- loss cooldown is inactive
- regime is acceptable and does not block new entries
- trend confirmation passes
- RSI is in a conservative momentum range
- volume confirmation passes
- spread is below ceiling
- ATR exists and is below volatility ceiling
- optional AI prediction, when supplied, is actionable and confirms probability
  and confidence thresholds
- stop-loss suggestion is valid
- reward-to-risk threshold is met

If any check fails, the strategy emits HOLD with explicit reasons.

## Safety Controls

The strategy is long-only. It never emits SELL for short exposure, never
averages down when an open base position is present, requires an ATR-based stop
suggestion for BUY, and honors cooldown after losses.

Stop and target values are advisory metadata for future risk modules. Stage 021
does not size positions, approve risk, create orders, call exchange adapters, or
execute trades.

## Operating Limits

This strategy is not a profitability claim. It is deterministic Stage 021
strategy logic intended for tests, backtesting, and later risk-engine
integration. Live trading remains disabled.
