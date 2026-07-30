# Cross-Asset Correlation Intelligence

Stage 066 adds advisory cross-asset correlation intelligence. It monitors
relationships between crypto assets, crypto sectors, and traditional-market
references using supplied return series.

The module does not fetch market data, call exchanges, call providers, create
signals, approve risk, create order intents, submit orders, cancel orders, or
execute trades.

## Inputs

`CrossAssetReturnSeries` contains:

- symbol
- aligned return observations
- asset class
- data-quality status
- observed timestamp
- source reference
- stale flag

The default tracked set includes BTC, ETH, Nasdaq, gold, DXY, and bond yields.
Additional crypto-sector series can be supplied by deterministic fixtures or
future upstream modules.

## Outputs

`evaluate_cross_asset_correlation` emits a
`CrossAssetCorrelationReport` containing:

- correlation matrix
- diversification opportunities
- correlation risk alerts
- quality flags
- source references
- audit payload

Alerts include high concentration, macro-risk linkage, insufficient samples,
and stale or rejected inputs.

## Operating Limits

- No profit is guaranteed.
- Correlation intelligence is advisory context only.
- Correlation alerts cannot bypass the Risk Management Engine.
- Poor-quality, stale, missing, or under-sampled inputs fail closed.
- Diversification opportunities are not allocation changes or trading
  instructions.
- Tests use deterministic fixtures and require no real credentials, provider
  access, exchange access, or network calls.
