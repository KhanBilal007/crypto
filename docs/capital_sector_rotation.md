# Capital and Sector Rotation

Stage 055 adds an advisory capital and sector rotation engine. It evaluates
supplied, normalized flow evidence for major crypto buckets and sectors, then
emits a capital flow map, rotation probability, sector-strength rankings,
risk-off score, confidence, reasons, and quality status.

The engine does not call exchanges, ETF providers, fund-flow vendors, market
data providers, blockchains, or any external service. All inputs are supplied by
deterministic fixtures or future stored provider outputs.

## Inputs

`CapitalFlowObservation` contains normalized `Decimal` scores between `0` and
`1` for:

- Inflow
- Outflow
- Momentum
- Liquidity
- Relative strength

Stage 055 tracks BTC, ETH, large caps, mid caps, small caps, stablecoins, AI,
RWA, Layer 2, gaming, DeFi, infrastructure, privacy, DePIN, and meme sectors.
Each observation carries a bucket, `DataQualityStatus`, `observed_at`,
`source_ref`, and stale flag.

## Outputs

`assess_capital_rotation` returns `CapitalRotationAssessment` with:

- `capital_flow_map`: per-bucket flow state such as strong inflow or outflow
- `rotation_probability`: deterministic rotation likelihood from flow
  dispersion and net-flow imbalance
- `sector_strength`: ranked bucket strengths
- `leading_bucket` and `lagging_bucket`
- `risk_off_score`: stablecoin pressure plus risk-asset weakness
- `mode`: risk-on, risk-off, sector rotation, neutral, or unknown
- `confidence`, `reasons`, `rejection_reasons`, `quality`, and audit payload

## Safety Limits

Capital rotation output is advisory context only. It cannot create strategy
signals, approve risk, create order intents, submit orders, execute trades, call
exchanges, call providers, or enable live trading.

Missing BTC, ETH, or stablecoin evidence, insufficient bucket coverage, stale or
rejected inputs, low confidence, and elevated risk-off flow fail closed. Degraded
inputs remain visible but are not actionable context.

No profit is guaranteed. Future strategy or execution behavior must still pass
the Risk Management Engine.
